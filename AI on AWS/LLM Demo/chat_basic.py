"""Very basic chat with a local Ollama model (default: phi4-mini).

Usage:
    python chat.py                 # uses phi4-mini
    python chat.py llama3.2        # use another model
"""

import json
import sys
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "phi4-mini"


def ask(messages):
    """Send the conversation to Ollama and stream the reply to the screen."""
    payload = json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode()
    request = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )

    reply = ""
    with urllib.request.urlopen(request) as response:
        for line in response:  # Ollama sends one JSON object per line
            chunk = json.loads(line)
            piece = chunk.get("message", {}).get("content", "")
            print(piece, end="", flush=True)
            reply += piece
    print()
    return reply


def main():
    print(f"Chatting with '{MODEL}'. Type 'exit' to quit.\n")
    messages = []  # conversation history so the model remembers context

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        print("AI: ", end="")
        reply = ask(messages)
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
