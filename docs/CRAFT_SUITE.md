# Optional Craft Suite handoff (v1.1.0)

**The integration is intentionally non-destructive and does not require Craft Suite.**

1. In Settings, enter the Craft Suite homepage's actual LAN URL. No port is hard-coded.
2. Open **Editorial & Craft Handoff** in the navigation tree.
3. Paste writing or copy from a Forge work area (creator, polisher, draft, prose, Weaver).
4. Optionally request an **editorial critique** or a **suggested revised passage** from the currently configured model. The original remains unchanged. A suggestion must be copied/accepted manually.
5. Export the passage to **HTML**, **Markdown**, or **plain text**, then click **Open Craft Suite** and import into WordCraft or another tool manually.

HTML export preserves paragraph breaks or poetry stanza and line breaks and includes a printable stylesheet. All export is performed in the user's browser; Kayock Writer does not push manuscripts to another LAN service.

**Not claimed:** there is no verified direct Craft Suite/WordCraft API, round-trip syncing, server-side document editing, DOCX generation, or guaranteed one-click import. These require inspecting and testing Craft Suite's actual supported endpoints.

No Craft Suite process is started, installed, restarted, or modified by Kayock Writer.
