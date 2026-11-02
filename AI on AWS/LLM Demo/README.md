# LLM Demo: Local Chat with Ollama + Tools

A small Python chat program that talks to a **local LLM running in Ollama** (default model: `phi4-mini`) and lets the model use **tools**:

- **Live web search** (DuckDuckGo, no API key needed) for current information
- **Docker troubleshooting**: list containers, inspect their state, and read their logs to find the root cause of a failure

You can use it from the **terminal** (`chat.py`) or from a **web UI** (`app.py`, built with Streamlit) where you can pick any model installed in Ollama.

Everything runs on your own laptop. No cloud LLM or API key needed.

## Files

| File | What it is |
|---|---|
| `chat_basic.py` | Step 1: plain chat with the model (no tools) |
| `chat_websearch.py` | Step 2: chat + live web search tool |
| `chat.py` | Step 3: terminal chat + web search + Docker tools |
| `app.py` | Step 4: Streamlit web UI for `chat.py`, with model picker and tool toggles |
| `requirements.txt` | Python packages to install |

## How it works

```
You ──► chat.py ──► Ollama (phi4-mini)
                        │
                        │ "I need a tool"  (tool call)
                        ▼
              chat.py runs the tool
         (web_search / docker commands)
                        │
                        │ tool result
                        ▼
                 Ollama writes the answer ──► You
```

1. Your question is sent to Ollama along with a description of the available tools.
2. If the model decides it needs a tool, it replies with a **tool call** (tool name + arguments) instead of an answer.
3. `chat.py` runs the matching Python function and sends the result back to the model.
4. This repeats until the model gives a normal answer.

The conversation history is kept, so the model remembers earlier messages.

## Setup on a new laptop

### 1. Prerequisites

- **Python 3.10 or newer**: check with `python3 --version`. Download from [python.org](https://www.python.org/downloads/) if needed.
- **Ollama**: install from [ollama.com/download](https://ollama.com/download), then open the Ollama app (or run `ollama serve`) so it's running in the background.
- **Docker Desktop** (only needed for the Docker tools): install from [docker.com](https://www.docker.com/products/docker-desktop/) and start it.

### 2. Download the model

```bash
ollama pull phi4-mini
```

Check that it's installed:

```bash
ollama list
```

### 3. Create a Python virtual environment

Go to the project folder:

```bash
cd "LLM Demo"
```

Create the virtual environment (only needed once):

```bash
python3 -m venv .venv
```

Activate it (needed every time you open a new terminal):

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)`.

### 4. Install the Python packages

```bash
pip install -r requirements.txt
```

### 5. Run it

**Option A: Web UI (Streamlit)**

```bash
streamlit run app.py
```

Your browser opens at http://localhost:8501. In the sidebar you can:

- **Model**: choose any model installed in Ollama (default `phi4-mini`). Models that can't use tools are marked `(no tools)` and chat without them.
- **🌐 Web search / 🐳 Docker tools**: turn each tool group on or off.
- **🗑️ Clear chat**: start a new conversation.

Each tool the model runs appears in the chat as a collapsible 🔧 box with its output, so you can see exactly what the model looked at.

**Option B: Terminal**

```bash
python chat.py
```

To use a different model (it must support tools; check with `ollama show <model>`):

```bash
python chat.py qwen3:14b
```

Type `exit` or `quit` to leave. When you're done, leave the virtual environment with `deactivate`.

## Example questions

**General (no tool):**
```
You: What is 2+2?
```

**Web search:**
```
You: What is the latest news about NASA this week?
  [tool] web_search({'query': 'latest news about NASA this week'})
AI: ...
```

**Docker:**
```
You: Which docker containers do I have?
You: Why did the container my-app stop? Find the root cause.
  [tool] inspect_container({'container': 'my-app'})
  [tool] get_container_logs({'container': 'my-app', 'tail': 100})
AI: ...
```

### Demo: a container that fails on purpose

```bash
docker run --name demo-crash alpine sh -c 'echo "Connecting to DB at db:5432..."; echo "ERROR: connection refused" >&2; exit 1'
```

Then ask: *"Why did demo-crash fail? Find the root cause."*

Remove it afterwards:

```bash
docker rm demo-crash
```

## Available tools

| Tool | What it does |
|---|---|
| `web_search(query)` | Top 5 DuckDuckGo results (title, link, snippet) |
| `list_containers()` | `docker ps -a`: all containers with status and ports |
| `inspect_container(container)` | Exit code, out-of-memory kill (`OOMKilled`), error, restart count, health |
| `get_container_logs(container, tail)` | The latest log lines (default 100) with timestamps |

The Docker tools are **read-only**. The model can't start, stop, or delete anything, and it can only run these fixed commands.

**Exit code cheat sheet:** `0` finished normally · `1` application error · `137` killed (out of memory only if `OOMKilled` is true) · `143` stopped with SIGTERM.

## Adding your own tool

1. Write a Python function that returns a string.
2. Describe it in the `TOOLS` list (name, description, parameters).
3. Register it in `AVAILABLE_TOOLS`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Connection refused` / `urlopen error` | Ollama isn't running: open the Ollama app or run `ollama serve` |
| `model "phi4-mini" not found` | Run `ollama pull phi4-mini` |
| `ModuleNotFoundError: No module named 'ddgs'` | Activate the venv (`source .venv/bin/activate`), then `pip install -r requirements.txt` |
| `Cannot connect to the Docker daemon` | Start Docker Desktop |
| `streamlit: command not found` | Activate the venv first, or run `python -m streamlit run app.py` |
| Web UI says "Can't reach Ollama" | Start Ollama, then refresh the page |
| A newly pulled model is missing from the list | The list refreshes every 60 seconds; wait, or restart Streamlit |
| The model prints raw JSON or gives weak answers | Small models are unreliable with tools; try a bigger one like `qwen3:14b` |
| Web search errors or returns nothing | DuckDuckGo may be rate-limiting you; wait a minute and retry |

**Note:** `phi4-mini` sometimes writes tool calls as plain JSON text instead of real tool calls. `chat.py` detects and runs these anyway.
