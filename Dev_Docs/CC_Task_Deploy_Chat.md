# CC Task: Deploy Conversation Engine + CLI Chat

## What this is

Four files that add the conversation engine, context construction, Ollama client, and CLI chat interface. After deployment, you can talk to the entity from the terminal.

## Files to deploy

Copy these into the existing project, preserving structure:

```
tir/
    cli_chat.py
    engine/
        __init__.py
        ollama.py
        context.py
        conversation.py
```

The `tir/` directory already exists from Phase 1 Step 1. Add the `engine/` subdirectory and `cli_chat.py` alongside the existing files.

## Prerequisites

- Phase 1 Step 1 (database layer) must be deployed and verified
- At least one user must exist (created via admin CLI)
- soul.md must be in the project root
- Ollama must be running with gemma4:26b available
- `requests` package installed (should be from requirements.txt)

## Verify — check Ollama is running

```bash
curl http://localhost:11434/api/tags | python3 -c "import json,sys; print([m['name'] for m in json.load(sys.stdin)['models']])"
```

Should show gemma4:26b in the list.

## Verify — check soul.md exists

```bash
cat soul.md
```

Should display the seed identity text.

## Verify — run the CLI chat

```bash
python -m tir.cli_chat
```

Expected behavior:
1. Prints "Starting new conversation." (or "Resuming conversation..." if one exists)
2. Prints "Chatting as Lyle. Type /quit to exit, /new for new conversation."
3. Shows a prompt: `Lyle: `
4. Type a message, press enter
5. Wait a few seconds (model generation time)
6. Entity responds with `Assistant: <response>`
7. Conversation continues

Test conversation:
```
Lyle: Hello
(wait for response)
Lyle: What do you know about yourself?
(wait for response — she should reference her soul.md identity)
Lyle: /info
(shows conversation ID, start time, message count)
Lyle: /quit
(ends conversation, exits)
```

## Verify — messages persisted

After the test conversation:

```bash
sqlite3 data/prod/archive.db "SELECT role, substr(content, 1, 80) FROM messages ORDER BY timestamp;"
sqlite3 data/prod/working.db "SELECT role, substr(content, 1, 80) FROM messages ORDER BY timestamp;"
```

Both databases should show the same messages.

## Debug mode

If something goes wrong, run with debug logging:

```bash
python -m tir.cli_chat --debug
```

This shows the full context construction and Ollama call details.

## Common issues

- **"No users exist"**: Run `python -m tir.admin add-user Lyle --admin` first
- **"soul.md not found"**: Make sure soul.md is in the project root (same level as the `tir/` directory)
- **Connection refused to Ollama**: Check `ollama serve` is running, check OLLAMA_HOST in config.py
- **Timeout**: gemma4:26b can take 10-30 seconds for longer responses. The timeout is set to 120s.
- **"think" field warning**: If Ollama warns about the `think` parameter, it's fine — some versions ignore it silently. If responses are very slow (40s+), the think parameter isn't being respected and reasoning tokens are being generated. Check Ollama version.

## What NOT to do

- Do not modify db.py or config.py
- Do not add tools or retrieval — this is the minimal pipeline
- Do not change the system prompt construction — it's intentionally minimal

## What comes next

After verifying she talks:
- Phase 2: ChromaDB + chunking + retrieval (she remembers)
- Then: iMessage adapter (she texts)
