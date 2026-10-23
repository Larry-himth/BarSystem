# Bar POS & Management System

POS and accountability system for a single bar in Uganda. It replaces notebook-based
stock, sales, credit-tab, and cash/MoMo reconciliation with an offline-first worker
web app and a lightweight owner mobile app.

This repository is built in phases. See `bar-pos-agent-prompt.md` for the full brief
and `docs/` for architecture, data model, API, and testing notes.

## Repository layout

```
bar-pos/
├── backend/      Django 5 + DRF REST API
├── worker-web/   React + Vite PWA used at the counter
├── boss-app/     Flutter app (Android-first) used by the owner
└── docs/         Architecture, data model, API, and testing documentation
```

> Setup instructions are added as each phase is completed.
