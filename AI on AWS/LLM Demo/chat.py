"""Basic chat with a local Ollama model (default: phi4-mini) plus tools:
live web search, and read-only Docker tools (list, inspect, logs) for troubleshooting.

Setup (once):
    pip install ddgs

Usage:
    python chat.py                 # uses phi4-mini
    python chat.py llama3.2:3b     # use another model (it must support tools)
"""

import json
import re
import subprocess
import sys
import urllib.request
from datetime import date

from ddgs import DDGS

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "phi4-mini"

SYSTEM_PROMPT = (
    f"You are a helpful assistant. Today's date is {date.today()}. "
    "If the question needs current or recent information (news, prices, weather, "
    "sports, latest versions, etc.), call the web_search tool, then answer using "
    "the results and mention the sources. "
    "For Docker questions, use the Docker tools: list_containers to find containers, "
    "inspect_container for exit code / OOM / restarts, and get_container_logs for errors. "
    "Base the root cause only on what the tools return, quote the relevant log lines, "
    "and suggest a fix. Exit codes: 0 = finished normally; 1 = application error; "
    "137 = SIGKILL: out of memory ONLY if OOMKilled is true, otherwise it was killed "
    "from outside (docker stop/kill, Docker restart); 143 = stopped with SIGTERM. "
    "Otherwise answer directly."
)


# ---------- Tools ----------

def web_search(query, max_results=5):
    """Search the web with DuckDuckGo and return the top results as text."""
    results = DDGS().text(query, max_results=max_results)
    if not results:
        return "No results found."
    return "\n\n".join(f"{r['title']}\n{r['href']}\n{r['body']}" for r in results)


def run_docker(*args, limit=4000):
    """Run a read-only docker command and return its output (trimmed for the model)."""
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=30
    )
    output = (result.stdout + result.stderr).strip() or "(no output)"
    # Keep the end of long output: for logs, the latest lines matter most
    return output if len(output) <= limit else "...(trimmed)...\n" + output[-limit:]


def list_containers():
    """List all Docker containers (running and stopped) with their status."""
    return run_docker(
        "ps", "-a", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
    )


def get_container_logs(container, tail=100):
    """Fetch the most recent log lines of a container."""
    return run_docker("logs", "--tail", str(int(tail)), "--timestamps", container)


def inspect_container(container):
    """Get a container's state: exit code, OOM kill, errors, restarts, health."""
    return run_docker(
        "inspect", "--format",
        "Status: {{.State.Status}}\nExitCode: {{.State.ExitCode}}\n"
        "OOMKilled: {{.State.OOMKilled}}\nError: {{.State.Error}}\n"
        "StartedAt: {{.State.StartedAt}}\nFinishedAt: {{.State.FinishedAt}}\n"
        "RestartCount: {{.RestartCount}}\nImage: {{.Config.Image}}\n"
        "Health: {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
        container,
    )


# Description of the tool that the model sees
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for up-to-date information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_containers",
            "description": "List all Docker containers on this machine with their status.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_container_logs",
            "description": "Get the most recent log lines of a Docker container.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string", "description": "Container name or ID"},
                    "tail": {"type": "integer", "description": "Number of lines (default 100)"},
                },
                "required": ["container"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_container",
            "description": "Get a Docker container's state: exit code, OOM kill, error, restarts, health.",
            "parameters": {
                "type": "object",
                "properties": {
                    "container": {"type": "string", "description": "Container name or ID"}
                },
                "required": ["container"],
            },
        },
    },
]

# Maps tool names to the Python functions that run them
AVAILABLE_TOOLS = {
    "web_search": web_search,
    "list_containers": list_containers,
    "get_container_logs": get_container_logs,
    "inspect_container": inspect_container,
}
NO_ARG_TOOLS = {"list_containers"}


# ---------- Talking to Ollama ----------

def looks_like_json(text):
    return text.lstrip()[:1] in ("[", "{")


def parse_text_tool_calls(text):
    """Pull tool calls out of JSON the model wrote as plain text."""
    decoder = json.JSONDecoder()
    found, pos = [], 0
    while pos < len(text):
        start = min((i for i in (text.find("[", pos), text.find("{", pos)) if i != -1), default=-1)
        if start == -1:
            break
        try:
            obj, pos = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            pos = start + 1
            continue
        found += obj if isinstance(obj, list) else [obj]

    calls = []
    for item in found:
        if not isinstance(item, dict):
            continue
        func = item.get("function", item)
        name = func.get("name")
        args = func.get("arguments") or func.get("parameters") or {}
        call = {"function": {"name": name, "arguments": args}}
        if name in AVAILABLE_TOOLS and call not in calls:
            calls.append(call)

    # Broken JSON: still catch calls to tools that need no arguments
    if not calls:
        for name in re.findall(r'"name"\s*:\s*"(\w+)"', text):
            if name in NO_ARG_TOOLS:
                calls.append({"function": {"name": name, "arguments": {}}})
                break
    return calls


def ask(messages):
    """Send the conversation to Ollama, stream the reply, and return the full message."""
    payload = json.dumps(
        {"model": MODEL, "messages": messages, "tools": TOOLS, "stream": True}
    ).encode()
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )

    content = ""
    tool_calls = []
    with urllib.request.urlopen(request) as response:
        for line in response:  # Ollama sends one JSON object per line
            message = json.loads(line).get("message", {})
            content += message.get("content", "")
            tool_calls += message.get("tool_calls", [])
            # Hide the reply while it looks like a JSON tool call written as text
            if not looks_like_json(content):
                print(message.get("content", ""), end="", flush=True)

    # Some small models (like phi4-mini) write tool calls as plain JSON text
    if not tool_calls:
        tool_calls = parse_text_tool_calls(content)
        if not tool_calls and looks_like_json(content):
            print(content, end="")
    print()

    reply = {"role": "assistant", "content": content}
    if tool_calls:
        reply["tool_calls"] = tool_calls
    return reply


def run_tool(call):
    """Run one tool call requested by the model and return its output as text."""
    name = call["function"]["name"]
    args = call["function"]["arguments"]
    if isinstance(args, str):
        args = json.loads(args)
    print(f"  [tool] {name}({args})")

    func = AVAILABLE_TOOLS.get(name)
    if func is None:
        return f"Error: unknown tool '{name}'"
    try:
        return func(**args)
    except Exception as e:
        return f"Error running {name}: {e}"


def main():
    print(f"Chatting with '{MODEL}' (web search enabled). Type 'exit' to quit.\n")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # Keep going until the model answers without asking for a tool
        while True:
            print("AI: ", end="")
            reply = ask(messages)
            messages.append(reply)
            if "tool_calls" not in reply:
                break
            for call in reply["tool_calls"]:
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": call["function"]["name"],
                        "content": run_tool(call),
                    }
                )


if __name__ == "__main__":
    main()
