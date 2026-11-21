# Kayock Writer v1.1.0 upgrade notes

- Adds **Editorial & Craft Handoff**: optional, on-demand model critique; suggested revisions remain separate from original writing.
- Adds browser-only HTML, Markdown, and plain-text downloads for transfer to Craft Suite/WordCraft. The optional Craft Suite URL opens in a separate tab; no unverified API call is made.
- Adds a non-destructive **Linux clone/install workflow**, with no privileged operation and no automatically enabled services.
- Preserves all 10 profile definitions, story gate logic, storage schema, provider settings, and original v1.0.0 Forge functions.
- Maintains Python 3.9+ and zero external dependencies.
- No new authentication gates or changes to running LAN services. Existing v1 security caveat remains: only run on a trusted LAN; consider a reverse proxy with access controls for shared environments.
- Private poems are excluded from the **public source ZIP and GitHub staging directory**. An author's private add-on ZIP is provided separately.
- Future releases should examine original Craft Suite APIs before promising direct transfers.
