# ShellMate

A split-screen, multi-tab network terminal with a built-in agentic AI copilot. Built for network engineers working with Cisco switches, routers, firewalls and similar devices.

![ShellMate welcome screen](docs/screenshot-welcome.png)

## What it does

- **Multi-tab SSH terminal** — connect to multiple network devices simultaneously, each in its own tab with an independent session, buffer and WebSocket
- **AI chat copilot** — Claude, OpenAI, xAI Grok, DeepSeek or local Ollama models see your live terminal output and answer questions about what's on screen
- **Tshoot / Learn mode toggle** — single pill in the tab bar flips the AI persona between *Troubleshoot* (terse, fix-it-now) and *Learn* (patient mentor that explains the why)
- **Knowledge-base augmentation (Chroma DB)** — point ShellMate at a Chroma vector store of your design guidelines and matching snippets are auto-retrieved and injected into every AI prompt; silently disabled when not configured
- **Configurable provider keys** — set Anthropic / OpenAI / xAI / DeepSeek / Ollama / Chroma credentials in the Settings panel as well as `.env`; the UI shows *"Already preconfigured by env variable"* when an env var is the active source
- **Command suggestions** — the AI suggests CLI commands you can approve with one click; dangerous commands get a confirmation prompt
- **Saved connection profiles** — save device details (no passwords stored) for one-click reconnect from the welcome screen
- **Session-aware context** — use `/context all` or `/context 2` to pull in other tabs; the AI always knows which tab is active
- **Tab management** — drag to reorder, right-click context menu, `Ctrl+1–9` shortcuts, `Ctrl+T`/`Ctrl+W`
- **Settings panel** — font, size, colour scheme (Deep Space, Solarized Dark, Nord, One Dark, Gruvbox, Dracula, Monokai), cursor, scrollback, UI text size, AI provider keys, Chroma DB endpoint
- **Conclude to Jira** — bundle session transcripts + chat into a Jira ticket (or comment on an existing one) with one click
- **Light / dark theme** — toggle from the sidebar
- **Smart copy/paste** — `Ctrl+C` (smart — copies selection or passes SIGINT), `Ctrl+Shift+C/V`, right-click paste dialog
- **Session logging** — optional per-session file logging to a configurable directory

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI · uvicorn · paramiko · pyserial |
| Frontend | Vanilla JS · xterm.js · HTML/CSS |
| AI | Claude · OpenAI · xAI Grok · DeepSeek · Ollama (local) |
| Knowledge base | Chroma vector DB (optional) |

## Getting started

### Requirements

- Python 3.11+
- Network access to an SSH device (or use localhost for testing)
- An API key for at least one of Anthropic, OpenAI, xAI, DeepSeek, **or** [Ollama](https://ollama.ai) running locally
- *(Optional)* a [Chroma](https://www.trychroma.com/) server hosting a `design_guidelines` collection if you want vector-RAG augmentation

### Install

```bash
git clone https://github.com/sjohnston1972/shellmate.git
cd shellmate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY (or any of OPENAI_API_KEY, XAI_API_KEY, DEEPSEEK_API_KEY)
# or leave them all blank and use Ollama
```

Anything in `.env` can be overridden at runtime in **Settings → AI Providers** and
**Settings → Knowledge Base (Chroma DB)**. The hierarchy is:

1. Value saved in the Settings panel (stored in `settings.json`) wins
2. Falls back to the matching `.env` variable
3. If neither is set, the provider is simply unavailable

For a Chroma-backed knowledge base, set `CHROMA_URL` (e.g. `http://localhost:8000`)
and `CHROMA_COLLECTION` (defaults to `design_guidelines`). When unset, ShellMate
silently skips the lookup — there's no penalty for leaving it disabled.

### Run

```bash
python run.py
```

ShellMate starts a local web server and opens your browser to `http://localhost:8765` automatically.

### Run with Docker

A `Dockerfile` and `docker-compose.yml` are included. The compose file attaches the
container to an external Docker network called `net_core`, so it pairs naturally
with a Cloudflare tunnel or any other reverse-proxy container on the same network.

```bash
cp .env.example .env       # add your keys
docker compose up -d --build
```

The container binds uvicorn to `0.0.0.0:8765`, mounts `./profiles` and `./logs`
for persistence, and exposes `8765:8765` for direct local access. To reach an
Ollama instance on the host, set `OLLAMA_HOST=http://host.docker.internal:11434`
(or the LAN IP of the box running Ollama) in `.env`.

If you front the container with a TLS reverse proxy, the WebSocket clients pick
`wss://` automatically — no extra configuration needed.

## Usage

| Action | How |
|---|---|
| New connection | Click **+ New** in the tab bar, or `Ctrl+T` |
| Quick connect | Click a saved device tile on the welcome screen |
| Switch AI mode | Click the **MODE** pill in the tab bar to flip between *Tshoot* and *Learn* |
| Pick AI model | Use the model dropdown in the chat header (cloud + local groups) |
| Switch tab | Click the tab, or `Ctrl+1` – `Ctrl+9` |
| Close tab | Click **×** on the tab, or `Ctrl+W` |
| Reorder tabs | Drag and drop |
| Ask the AI | Type in the chat panel on the right |
| Include all tabs in AI context | Start message with `/context all` |
| Include a specific tab | Start message with `/context 2` |
| Run AI-suggested command | Click **Send** on the command block |
| Send the session to Jira | Click **Conclude** in the chat header |
| Copy terminal text | `Ctrl+C` (with selection), or `Ctrl+Shift+C` |
| Paste into terminal | `Ctrl+V` or right-click |
| Open settings | Gear icon in the left sidebar |
| Configure provider keys / Chroma | Settings → *AI Providers* and *Knowledge Base (Chroma DB)* |
| Toggle light/dark theme | Moon icon in the left sidebar |

## Project structure

```
shellmate/
├── run.py                     # Entry point — starts server, opens browser
├── requirements.txt
├── .env.example               # Configuration template
├── backend/
│   ├── app.py                 # FastAPI app, REST endpoints, WebSocket handlers
│   ├── config.py              # Loads .env config
│   ├── profiles.py            # Connection profile persistence
│   ├── settings_store.py      # Application settings persistence
│   ├── connections/
│   │   ├── manager.py         # Session lifecycle (create/track/destroy by UUID)
│   │   ├── ssh_handler.py     # paramiko SSH interactive shell
│   │   └── serial_handler.py  # pyserial console
│   ├── session/
│   │   └── buffer.py          # Per-session terminal I/O buffer
│   └── ai/
│       ├── router.py          # Routes to selected backend, builds session context, queries Chroma
│       ├── prompts.py         # Tshoot + Learn personas, context builder
│       ├── claude_client.py   # Claude API streaming client
│       ├── openai_client.py   # OpenAI streaming client
│       ├── xai_client.py      # xAI Grok streaming client
│       ├── deepseek_client.py # DeepSeek streaming client
│       ├── ollama_client.py   # Ollama streaming client
│       ├── chroma_client.py   # Optional Chroma vector-DB lookup (silently disabled if not configured)
│       └── summarize.py       # One-shot session summary used by Conclude → Jira
└── frontend/
    ├── index.html
    ├── css/style.css
    └── js/
        ├── connections.js     # Connection dialog + saved profiles
        ├── tabs.js            # Tab bar management + drag reorder
        ├── terminal.js        # xterm.js init, copy/paste, settings apply
        ├── mode.js            # Tshoot / Learn pill toggle, persists to localStorage
        ├── chat.js            # AI chat panel, command blocks, streaming
        ├── settings.js        # Settings panel (incl. provider keys + Chroma)
        ├── jira.js            # Conclude-session → Jira modal
        └── logs.js            # Logs panel
```

## Design

ShellMate uses the *Deep Space* design system — dark background, Space Grotesk headlines, Inter UI text, and JetBrains Mono for the terminal. Built to feel like a high-performance instrument, not a SaaS dashboard. A light theme is also available.

## Security

- **No built-in authentication.** ShellMate is an interactive SSH client, so anyone who reaches the web UI can launch sessions to any host the server can route to. Treat it like an open shell:
  - Local development (`python run.py`) binds to `127.0.0.1` only — fine for a single user on the same machine.
  - The Docker / `docker-compose.yml` path binds to `0.0.0.0:8765` so the container is reachable on its network. **Do not expose it directly to the public internet.** Put it behind something that authenticates users — Cloudflare Access, Tailscale, an SSO-aware reverse proxy, etc.
- **Passwords are never persisted and dropped from memory once the SSH session is open.** They're prompted on each new connection, used to complete the authentication handshake, then cleared — the long-lived session object holds an empty string in their place.
- **API keys** live in `.env` only — never in code, never in saved profiles.
- **Session buffers** are in-memory and cleared on disconnect, unless file logging is explicitly enabled.
- **Saved profiles** record host, port, username, and connection type so you can one-click reconnect. They never contain the password — that is always re-prompted.

## License

MIT
