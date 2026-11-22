# Installation guide

Kayock Writer is a self-contained Python application with **no third-party
dependencies** — anything that runs Python 3.9+ can host it, including the
machine that runs your model server.

## 1. Requirements

- Python 3.9 or newer (`python --version`)
- An **OpenAI-compatible chat endpoint** reachable from the machine running
  Kayock Writer. Any of these work out of the box:
  - **llama.cpp** `llama-server -m model.gguf --host 127.0.0.1 --port 8080`
  - **LM Studio** → Developer tab → Start Server (default `http://127.0.0.1:1234`)
  - **Ollama** → `ollama serve` (endpoint `http://127.0.0.1:11434`, chat path `/v1/chat/completions`)
  - **llamafile**, **vLLM**, **text-generation-webui** (OpenAI extension)
  - A hosted API that speaks the OpenAI chat protocol (set an API key)
- A browser on any machine in the LAN.

## 2. GitHub clone / optional non-destructive Linux install

Once a repository is created and this release is pushed, use its real URL:

```bash
git clone https://github.com/kayock/Kayock-Writer.git
cd Kayock-Writer
bash deploy/install-linux.sh
```

The helper copies application files into `$HOME/Applications/KayockWriter`
(default, overridable via `KAYOCK_WRITER_INSTALL_DIR`) without overwriting
`config.json` or the data folder. It does not run with sudo, enable services,
change firewalls, or start models. It prints the command to launch Writer.

Alternatively, use the Git clone in place; no install helper is required.

**Development release candidate testing:** GitHub Actions runs
tests/test_install_staging.py on Windows and Linux. On Linux it invokes
the real install-linux.sh helper **only with an explicitly set
temporary destination**, checks repeated install preservation of
config.json, private add-ons and writing data, and refuses a symlink
destination. On Windows it tests a clean copied-source startup, not
a Windows native installer. These checks **do not authorize or
perform any in-place production upgrade or rollback**. See
[release acceptance](RELEASE_ACCEPTANCE.md) for the remaining tests.

## 3. Start Kayock Writer

```bash
cd KayockWriter
python kayock_writer.py --base-url http://127.0.0.1:8080
```

Output:

```
Kayock Writer 1.1.0
  Serving on http://0.0.0.0:8765  (LAN: use this machine's IP)
  Data dir : .../KayockWriterData
  Model    : local-model @ http://127.0.0.1:8080
  Press Ctrl+C to stop.
```

Open `http://localhost:8765` on the server machine, or
`http://<server-LAN-IP>:8765` from any other device.

Sanity check without starting the server:

```bash
python kayock_writer.py --check
# prints resolved host/port, data dir, model endpoint and health probe result
```

## 3. Configuration reference

Precedence: **CLI flags → environment variables → `config.json` → defaults.**
`config.json` is created next to `kayock_writer.py` the first time you save
settings in the UI (or copy `config.example.json`).

| Setting | CLI flag | Env var | Config key | Default |
|---|---|---|---|---|
| Bind address | `--host` | `KAYOCK_WRITER_HOST` | `server.host` | `0.0.0.0` (LAN-reachable) |
| Port | `--port` | `KAYOCK_WRITER_PORT` | `server.port` | `8765` |
| Data folder | `--data-dir` | `KAYOCK_WRITER_DATA` | `paths.data_dir` | `./KayockWriterData` |
| Model base URL | `--base-url` | `KAYOCK_MODEL_BASE_URL` | `model.base_url` | `http://127.0.0.1:8080` |
| Model name | `--model` | `KAYOCK_MODEL_NAME` | `model.model` | `local-model` |
| Chat path | — | — | `model.chat_path` | `/v1/chat/completions` |
| Health path | — | — | `model.health_path` | `/health` |
| Health mode | — | — | `model.health_kind` | `auto` (`openai_models`, fallback `http_status`) |
| API key | — | `KAYOCK_MODEL_API_KEY` | `model.api_key` | empty |
| Request timeout | — | — | `model.timeout_seconds` | `420` |
| Approval phrases | — | — | `writing.require_approval_phrase` | `true` |
| Default author | — | — | `writing.default_author` | `Eric Z. Fox` |

Model endpoint changes made in **Settings → Model endpoint** save to
`config.json` and take effect immediately (host/port need a restart).

The API key is never printed, logged, or sent to the browser. Prefer the
environment variable; if you store it in `config.json`, protect that file.

## 4. LAN access notes

- Default bind `0.0.0.0` exposes the app to your local network. Use
  `--host 127.0.0.1` to keep it local-only.
- There is no authentication — anyone on the LAN can read and write the
  writing data. Keep it on a trusted network.
- If other machines cannot connect, allow the port through the firewall:
  - **Windows**: `netsh advfirewall firewall add rule name="Kayock Writer" dir=in action=allow protocol=TCP localport=8765`
  - **Linux (ufw)**: `sudo ufw allow 8765/tcp`
  - **macOS**: System Settings → Network → Firewall → allow python.
- "Open folder on server" buttons use the server machine's desktop opener
  (Explorer/Finder/xdg-open) when available; otherwise the app shows the
  folder path instead. Disable entirely with `server.allow_folder_open: false`.

## 5. Bringing your existing data

- **Novel Forge universes**: copy `FOXAI/NovelForge/*.json` into
  `<data_dir>/NovelForge/` (the `Markdown/` mirror regenerates on save).
- **Poems and short stories**: copy the `.md` drafts from
  `FOXAI/Projects/KayockWriter/Poetry/Drafts/` and
  `.../ShortStories/Drafts/` into the same folders under
  `<data_dir>/Projects/KayockWriter/`. The front-matter format is identical,
  so the archive groups versions exactly like FOXAI did.
- **Story Forge projects**: copy a whole project folder (with
  `project.kayock-writer.json`) into `<data_dir>/Projects/KayockWriter/`.
- **Private voice pack**: see docs/PRIVATE_VOICE_PACK.md.

## 6. Running as a service (optional)

```bash
# systemd (Linux)
[Unit]
Description=Kayock Writer
After=network.target
[Service]
WorkingDirectory=/opt/KayockWriter
Environment=KAYOCK_MODEL_BASE_URL=http://127.0.0.1:8080
ExecStart=/usr/bin/python3 kayock_writer.py
Restart=on-failure
[Install]
WantedBy=multi-user.target
```

Windows: create a shortcut to
`python kayock_writer.py --base-url http://127.0.0.1:8080` in
`shell:startup`, or use Task Scheduler.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| "model offline" badge | Check the endpoint with `python kayock_writer.py --check`; verify base URL, port, and that the model server is running. For Ollama keep the default chat path (`/v1/chat/completions`). |
| `HTTP 404` on chat | Wrong `model.chat_path` — OpenAI-compatible servers usually want `/v1/chat/completions`. |
| `HTTP 401` | Set the API key (Settings or `KAYOCK_MODEL_API_KEY`). |
| LAN device cannot connect | Bind host is `127.0.0.1`? Use `--host 0.0.0.0`. Firewall rule? See above. |
| Port already in use | `--port 9000` (or any free port). |
| Long generations cut off | Raise `model.timeout_seconds` (default 420 s) — local models on CPU can be slow for `Long` story output. |
