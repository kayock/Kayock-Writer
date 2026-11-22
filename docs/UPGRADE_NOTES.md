# Kayock Writer v2.0.0 upgrade notes

- Reports application version **2.0.0** from the centralized `app.__version__` constant (API status, CLI, and Studio status).
- Adds **Editorial Council**, **Author Decision Board**, **Controlled Revision Workspace**, and **Full-Book Assembly** with DOCX / EPUB 3 / PDF publishing (optional JPEG cover; optional Unicode TrueType for PDF).
- Integrates optional model routing modes:
  - `model.selection_mode`: `fixed` (default) or `ollama_active` (use currently loaded Ollama model via `/api/ps`; never start, stop, or pull models)
  - `model.disable_thinking`: when true, requests include `think:false` so reasoning models keep token budget for writing
- Existing `config.json` files remain valid. Unknown older keys are ignored; new keys use the defaults above when absent.
- Linux `deploy/install-linux.sh` continues to preserve `config.json`, private add-ons, and writing data.
- Maintains Python 3.9+ and zero external Python dependencies.
- No new authentication gates. Existing LAN security caveat remains: only run on a trusted LAN.
