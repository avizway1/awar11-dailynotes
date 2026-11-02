"""Basic chat with a local Ollama model (default: phi4-mini) plus a live web search tool.

Setup (once):
    pip install ddgs

Usage:
    python chat.py                 # uses phi4-mini
    python chat.py llama3.2:3b     # use another model (it must support tools)
"""

import json
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
    "the results and mention the sources. Otherwise answer directly."
)


# ---------- Tools ----------

def web_search(query, max_results=5):
    """Search the web with DuckDuckGo and return the top results as text."""
    results = DDGS().text(query, max_results=max_results)
    if not results:
        return "No results found."
    return "\n\n".join(f"{r['title']}\n{r['href']}\n{r['body']}" for r in results)


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
    }
]

# Maps tool names to the Python functions that run them
AVAILABLE_TOOLS = {"web_search": web_search}


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
    if not tool_calls and looks_like_json(content):
        tool_calls = parse_text_tool_calls(content)
        if not tool_calls:
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
