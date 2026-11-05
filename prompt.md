# MEGA PROMPT: Bar POS & Management System

You are a senior full-stack engineer. Build the system described below, phase by phase, inside a git repository. Read this entire document before writing any code. Follow the **Working Rules** (section 13) strictly.

---

## 1. Product summary

A POS and management system for **a single bar in Uganda** that replaces the manual notebook-based handling of the bar. It tracks stock inventory, sales, payments, credit tabs and worker accountability.

Two sides:

| Side | Users | Platform | Purpose |
|---|---|---|---|
| **Worker side** | Bartenders / cashiers | **Website (PWA) served on localhost**, opened on a PC monitor at the counter | Record daily stock, sell, record deliveries/losses, close shift, submit accountability report |
| **Boss side** | Owner / manager | **Mobile app (React Native + Expo, Android first)** | Monitor sales, inventory, worker variances; approve shifts; approve restocking; confirm mobile money |

Core problem being solved: bars lose money through **missing stock, cash that doesn't match sales, uncollected credit, and unverifiable mobile money**. Every feature must serve one of those four.

## 2. Hard constraints (Uganda reality)

1. **Offline-first worker side.** Internet and power are unreliable. The worker website must keep working with no connection, queue everything locally, and sync automatically when online.
2. **Low data usage** on the boss app. Return summaries, paginate, avoid heavy payloads and images.
3. **Cheap Android phones** for the boss app. Keep it light.
4. **Workers have low tech literacy.** Big touch-friendly buttons, item pictures/icons, minimal typing, color-coded actions, very few screens.
5. **Currency is UGX** (Ugandan shilling). Store money as **integers** (no decimals, no floats).
6. **Timezone is Africa/Kampala.**
7. **Languages: English and Swahili are mandatory**, designed so Luganda can be added later without code changes.
8. **Mobile money (MTN MoMo / Airtel Money)**: customers simply send money to the boss's personal number. There is **no API integration**. The system records and reconciles it manually (see section 7).

## 3. Tech stack (use exactly this unless you flag a blocker)

- **Backend:** Python 3.12, Django 5, Django REST Framework, SimpleJWT, django-cors-headers, django-filter, drf-spectacular (OpenAPI docs). Database: **PostgreSQL** (SQLite allowed for the first local run via an environment variable, but the code must be Postgres-compatible).
- **Worker web app:** React + Vite + TypeScript, `vite-plugin-pwa` (service worker), **Dexie (IndexedDB)** for the offline store and sync queue, `react-router`, `i18next` + `react-i18next`, Tailwind CSS.
- **Boss app:** React Native with **Expo** + TypeScript, `expo-router`, `i18next`, `@tanstack/react-query`, `expo-secure-store`, `expo-notifications` (in-app polling first, push later).
- **Tooling:** pytest + pytest-django for backend tests, Vitest for worker web, ESLint + Prettier, `black` + `ruff` for Python, `.env` files with `.env.example`.

## 4. Architecture

```
┌──────────────────────────────┐        ┌──────────────────────────────┐
│ WORKER WEB APP (PWA)         │        │ BOSS MOBILE APP (Expo RN)    │
│ localhost:5173 on PC monitor │        │ Android, on boss's phone     │
│ - Offline-first              │        │ - Dashboard, approvals       │
│ - IndexedDB + sync queue     │        │ - Read-mostly, light on data │
└──────────────┬───────────────┘        └──────────────┬───────────────┘
               │ HTTPS/HTTP (REST + JWT)               │
               ▼                                       ▼
        ┌──────────────────────────────────────────────────┐
        │            DJANGO REST API (localhost:8000)      │
        │  auth/roles · inventory ledger · sales · shifts  │
        │  variance engine · reports · audit log · sync    │
        └──────────────────────┬───────────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   PostgreSQL DB     │
                    │ (append-only ledger)│
                    └─────────────────────┘
```

**Rules of the architecture:**
- The backend is the single source of truth. Both clients are thin consumers of the same REST API.
- **Stock is an append-only ledger** (`stock_movements`). Current stock = sum of movements. Never store an editable "current quantity" as the source of truth. A cached value for display is allowed only if it is derived from, and verified against, the ledger.
- **Idempotent writes:** every sale and stock movement is created with a **client-generated UUID**. If the same UUID arrives twice, the second request is accepted and ignored (returns the original record). This protects against double-counting during offline sync retries.
- **Locked records:** once a shift is `SUBMITTED`, nothing belonging to it can be edited by the worker. Corrections happen only as new `ADJUSTMENT` movements approved by a manager/owner.
- **Local development networking:** the boss app (on a real phone via Expo Go) reaches the API through the computer's LAN IP, not `localhost`. Make the API base URL configurable via env in both clients, and document how to find the LAN IP and run Django with `0.0.0.0:8000` (and set `ALLOWED_HOSTS` / CORS for dev).

## 5. Repository layout (monorepo)

```
bar-pos/
├── README.md
├── .gitignore
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── api.md
│   └── testing-guide.md
├── backend/            # Django project
├── worker-web/         # React + Vite PWA
└── boss-app/           # Expo React Native
```

## 6. Data model (implement as Django models)

All tables have `id`, `created_at`, `updated_at` unless stated. Money = integer UGX. Quantities = **integers in the smallest base unit** (no floats, no decimals): beer/soda/water base unit = 1 piece; spirits base unit = 1 ml (a 750 ml bottle = 750, a 25 ml tot = 25). Unit conversion is done through `ItemUnit.qty_in_base_unit`.

**Users and access**
- `User` (custom): `name`, `username`, `pin_hash` (PIN login for workers; password or PIN for owner), `role` (`OWNER | MANAGER | BARTENDER`), `language` (`en | sw`), `is_active`.

**Catalog**
- `Item`: `name_en`, `name_sw`, `category` (beer, spirit, soft drink, water, snack, other), `base_unit` (the smallest tracked unit, e.g. bottle, can, tot), `buy_price`, `par_level` (minimum stock before restock), `icon/image` (optional), `is_active`.
- `ItemUnit`: `item`, `label` (e.g. Bottle, Tot, Crate), `qty_in_base_unit` (e.g. 1, 0.04, 12), `sell_price`, `can_sell` (bool), `can_buy` (bool). Example: Waragi base unit = bottle; Tot = 0.04 bottle at 1,500 UGX; Crate = 12 (buy only).

**Time boundary**
- `Shift`: `opened_by`, `opened_at`, `closed_at`, `submitted_at`, `approved_by`, `status` (`OPEN | SUBMITTED | APPROVED | DISPUTED`), `notes`. Only one `OPEN` shift at a time.

**Ledger (immutable: no update, no delete, enforce at model and API level)**
- `StockMovement`: `uuid` (unique, client-generated), `item`, `shift`, `qty_base` (signed), `type` (`OPENING | SALE | DELIVERY | SPILLAGE | COMP | ADJUSTMENT | CLOSING_COUNT`), `reason` (required for SPILLAGE, COMP, ADJUSTMENT), `created_by`, `created_at`.

**Selling**
- `Sale`: `uuid` (unique), `shift`, `total`, `created_by`, `created_at`, `voided_by` (nullable), `void_reason`, `voided_at`. Voids require a manager/owner PIN and write reversing ledger entries; sales are never deleted.
- `SaleLine`: `sale`, `item_unit`, `qty`, `unit_price`, `line_total`.
- `Payment`: `sale`, `method` (`CASH | MOMO | TAB`), `amount`, `momo_ref` (transaction ID or last digits + sender name, required for MOMO), `tab` (required for TAB).

**Credit**
- `Tab`: `customer_name`, `phone`, `balance` (derived from tab sales minus tab repayments).
- `TabPayment`: `tab`, `amount`, `method`, `received_by`, `shift`.

**Accountability**
- `ShiftReport`: `shift`, `expected_cash`, `declared_cash`, `cash_variance`, `expected_momo`, `momo_status` (`PENDING | CONFIRMED | DISPUTED`), `momo_confirmed_by`, `notes`.
- `CountVariance`: `shift`, `item`, `expected_qty`, `counted_qty`, `variance_qty`, `variance_ugx` (computed at buy price). **Computed by the server only; never accepted from a client.**

**Restocking**
- `RestockRequest`: `shift`, `status` (`PROPOSED | APPROVED | ORDERED | RECEIVED | REJECTED`), `approved_by`.
- `RestockLine`: `request`, `item`, `current_qty`, `par_level`, `suggested_qty`, `approved_qty`.

**Audit**
- `AuditLog`: `user`, `action`, `entity`, `entity_id`, `metadata` (JSON), `created_at`. Written for: logins, voids, discounts, price changes, adjustments, shift submit/approve, restock approvals. Append-only.

## 7. Core workflows

### 7.1 Daily shift (worker side)
1. **Open shift.** Worker logs in with PIN. System opens a shift. Worker performs the **opening count** (physical count per item), which creates `OPENING` movements. If it differs from the previous shift's closing count, flag it as a carry-over variance for the boss.
2. **Selling.** Big item grid, tap to add, choose unit (Bottle/Tot/etc.), choose payment: **Cash**, **Mobile Money** (must enter reference), or **Tab** (select/create customer). Completing the sale creates `Sale`, `SaleLine`, `Payment`, and negative `SALE` movements. Works fully offline.
3. **During the shift.** Worker can record **deliveries**, **spillage/breakage**, and **complimentary** drinks. Each requires a reason code. Discounts, price overrides and voids require a manager PIN.
4. **Close shift.** Worker does a **blind closing count**: the UI must NOT show expected stock until the count is submitted (the server must also not expose expected values to the BARTENDER role before submission).
5. **Auto-balance.** Server computes:
   - Expected stock per item = opening + deliveries − sales − recorded losses/comps ± approved adjustments.
   - Variance = counted − expected, in units and UGX.
   - Expected cash = sum of CASH payments (minus voids) + TAB repayments received in cash. Cash variance = declared − expected.
   - Expected MoMo = sum of MOMO payments.
6. **Submit accountability report.** One action. Report becomes locked and is pushed to the boss's side.

### 7.2 Boss review (boss app)
1. Sees pending shift reports with a clear summary: total sales, cash expected vs declared, MoMo expected, top variances in UGX.
2. **MoMo confirmation:** the boss compares expected MoMo against his own MoMo statement and taps **Confirm** or **Dispute** with a note.
3. Boss **approves** or **disputes** the shift (with a note).
4. Boss sees the **system-proposed restock list** (items below `par_level`), edits quantities, and **approves**. **Restocking can only be approved after the previous shift is `APPROVED`.** This enforces accountability before restocking.
5. Boss sees live dashboards: today's sales, current stock levels, low-stock items, void counts per worker, tab balances (who owes what), and variance trends.

### 7.3 Offline sync (worker side)
- All writes go to Dexie first with a `pending` flag and client UUID, and are then sent in batches to `POST /api/sync/`.
- The server processes the batch in order and returns per-record results (`created | duplicate | rejected` with reason).
- The UI always shows a clear **online/offline indicator** and a **"X records waiting to sync"** counter.
- On rejection, the record is kept locally in a "needs attention" list, never silently dropped.
- Catalog data (items, units, prices) is cached locally and refreshed when online.

## 8. API (REST, JSON, JWT, versioned under `/api/v1/`)

Implement at minimum, with permission classes per role:

- `POST /auth/login/` (username + PIN), `POST /auth/refresh/`, `GET /auth/me/`
- `GET /items/`, `POST /items/` (OWNER/MANAGER), `PATCH /items/{id}/`, `GET/POST /item-units/`
- `POST /shifts/open/`, `GET /shifts/current/`, `POST /shifts/{id}/count/` (opening or closing count), `POST /shifts/{id}/submit/`, `POST /shifts/{id}/approve/`, `POST /shifts/{id}/dispute/`, `GET /shifts/` (filters: status, date)
- `POST /sales/`, `POST /sales/{id}/void/` (manager PIN), `GET /sales/` (filters)
- `POST /stock-movements/` (delivery, spillage, comp), `POST /stock-movements/adjust/` (MANAGER/OWNER)
- `GET /stock/` (current stock per item, derived from the ledger; role-restricted as per the blind-count rule)
- `GET/POST /tabs/`, `POST /tabs/{id}/payments/`
- `GET /shifts/{id}/report/`, `POST /shifts/{id}/momo-confirm/`
- `GET /restock/proposed/`, `POST /restock/`, `POST /restock/{id}/approve/`
- `GET /dashboard/summary/` (owner: today's sales, low stock, pending reports, void counts, tab balances)
- `POST /sync/` (batch sync for the worker PWA)
- `GET /audit-log/` (OWNER only)
- OpenAPI schema at `/api/schema/` and docs at `/api/docs/`.

Return consistent error shapes `{ "code": "...", "message": "...", "details": {...} }`, and **translatable messages**.

## 9. Worker web app (React PWA) requirements

- Screens: **Login (PIN pad)** → **Open Shift + Opening Count** → **Sell** (main screen) → **Stock actions** (delivery/spillage/comp) → **Tabs** → **Close Shift (blind count)** → **Shift Summary & Submit**.
- Layout optimized for a **monitor and mouse/touch**: large buttons, high contrast, no tiny text.
- The Sell screen: category tabs at the top, item grid with name + price + icon, running order panel on the right, a payment bar at the bottom.
- Language switcher visible on every screen (EN / SW).
- Installable as a PWA; runs on `http://localhost:5173` (dev) and can be built (`npm run build`) and served locally.
- Clear, friendly, non-technical error messages. Never show stack traces to the worker.

## 10. Boss mobile app (Expo React Native) requirements

- Screens: **Login** → **Dashboard** → **Shift Reports** (list + detail with variance table) → **Approve / Dispute** → **MoMo Confirmation** → **Stock Levels** → **Restock Approval** → **Tabs (who owes)** → **Staff Performance** (sales, voids, variances per worker) → **Settings** (language, logout).
- Pull-to-refresh, cached data via react-query, graceful offline display of last-known data with a "last updated" time.
- Notifications: in-app polling for pending reports initially; design the code so push (FCM via Expo) can be added later without restructuring.
- Android first. Must run via Expo Go during development AND be buildable as an installable **APK** for testing (see Phase 5).

## 11. Internationalization

- Use `i18next` in both clients with locale files `en.json` and `sw.json`. **No hardcoded UI strings anywhere.**
- Item names carry `name_en` and `name_sw`; display uses the user's language with an English fallback.
- Server error messages use Django translations (`en`, `sw`).
- Format numbers/dates by locale; show money as `UGX 15,000`.
- Provide a Swahili translation for every string. Mark any translation you are unsure about with a `// TODO: native review` comment so a native speaker can verify it.

## 12. Security and integrity

- Hash PINs and passwords (Django's hashers). Rate-limit and temporarily lock accounts after repeated failed logins.
- Role-based permissions enforced **on the server**, never just hidden in the UI.
- BARTENDER cannot: see expected stock before submitting a closing count, edit submitted records, view other workers' reports, change prices, or see profit/buy prices.
- OWNER/MANAGER only: voids, discounts beyond a configured limit, adjustments, price changes, approvals.
- All ledger and audit tables are append-only.
- Secrets only in `.env`; commit `.env.example` only.
- Provide a management command for a **daily database backup** (`pg_dump` wrapper) and document it.

## 13. Working rules (follow strictly)

1. **First action: create the git repository.** Run `git init`, create the monorepo structure, a proper `.gitignore` (Python, Node, Expo, `.env`, `node_modules`, `__pycache__`, `*.sqlite3`), a `README.md`, and make the first commit on `main`: `chore: initial repository structure`.
2. **Git discipline:**
   - One **branch per phase**: `phase-1-backend-foundation`, `phase-2-...`, etc. Merge to `main` only after the phase's tests pass and the user confirms the phase works.
   - Use **Conventional Commits** (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`).
   - Small, frequent commits. Each commit must leave the project in a working state.
   - Tag completed phases: `v0.1-phase1`, `v0.2-phase2`, etc.
   - After each phase, give the user the exact commands to review history (`git log --oneline --graph`).
3. **Stop at the end of every phase.** Do not start the next phase until the user replies. At each stop, give:
   - What was built (short list).
   - **Exact commands to run it** (from a clean clone: install, migrate, seed, run).
   - **A manual test checklist** the user can follow, with expected results.
   - Known limitations.
4. **The user will test and report problems.** When the user reports a bug, reproduce it with a failing test first when practical, then fix it, commit with `fix:`, and explain the root cause in one or two sentences.
5. **Write tests as you build**, especially for: stock ledger math, unit conversion, idempotent sync, shift locking, variance calculation, permission rules. Do not move on with failing tests.
6. **Seed data:** provide `python manage.py seed_demo` that creates 1 owner, 1 manager, 2 bartenders (with PINs documented in the README for dev only), ~20 realistic Ugandan bar items (e.g. Nile Special, Club, Bell, Tusker, Uganda Waragi, Johnnie Walker, Coca-Cola, Fanta, Mineral water, Soda, Nyama choma snack) with units, prices and par levels, and optionally a few historical shifts so dashboards aren't empty.
7. **Explain as you go.** For each non-trivial piece of code, include brief comments on *why*, not just *what*. The user is a software engineering student and wants to understand the code.
8. **Do not over-build.** Stay within the current phase's scope. Do not add features not listed here without asking.
9. **If something is ambiguous or blocked, ask one clear question** instead of guessing silently. If you must make an assumption, state it in the phase summary.
10. **Keep docs in `docs/` up to date** as the system changes (architecture, data model, API, testing guide).

## 14. Build phases

**Phase 0: Repository and project skeletons**
Create the repo (rule 1), the three project skeletons (Django, Vite React PWA, Expo app), linting config, `.env.example` files, and a root `README.md` explaining how to run everything. Backend `GET /api/v1/health/` returns OK. *Done when:* all three skeletons start without errors.

**Phase 1: Backend foundation**
Custom user + roles + PIN auth (JWT), `Item`/`ItemUnit`, catalog API, admin site configured, seed command, tests for auth and unit conversion. *Done when:* the user can log in via API docs and manage items.

**Phase 2: Ledger, shifts and sales (the core)**
`Shift`, `StockMovement` (append-only), `Sale`/`SaleLine`/`Payment`, `current stock` derivation, open shift + opening count, selling (cash, MoMo with ref, tab), deliveries, spillage, comps, voids with manager PIN, idempotent UUID handling. *Done when:* a full simulated day can be run through the API and stock reconciles exactly. Heavy tests here.

**Phase 3: Shift close, variance engine and reports**
Blind closing count, server-side variance calculation, `ShiftReport`, submit/lock, approve/dispute, MoMo confirmation, restock proposal and approval (gated on approved shift), audit log. *Done when:* the end-to-end accountability flow works via API with correct UGX variances.

**Phase 4: Worker web app (offline-first PWA)**
All worker screens (section 9), Dexie store, sync queue and `/sync/` integration, online/offline indicator, PIN login, EN/SW i18n. *Done when:* the user can run a full shift in the browser, turn the internet off mid-shift, keep selling, reconnect, and see everything sync with no duplicates.

**Phase 5: Boss mobile app**
All boss screens (section 10), dashboards, approvals, MoMo confirmation, restock approval, staff performance, EN/SW i18n, tested on a real phone over LAN. **Also produce an installable Android APK for testing**: use Expo EAS Build with a `preview` profile (`eas build -p android --profile preview`, `buildType: apk` in `eas.json`), or if I cannot use EAS, a local build (`npx expo prebuild` then `./gradlew assembleRelease`). Give me complete step-by-step instructions for the route you choose, including account setup and which route is free. The API base URL must be editable on the boss app's login screen (a 'Server address' field) so the APK can point at my PC's LAN IP without rebuilding. *Done when:* the APK installs on my Android phone, connects to the backend over local Wi-Fi, and I can see a worker's submitted report and approve it.

**Phase 6: Hardening, translations and demo readiness**
Swahili translation review pass, error handling and empty states, backup command, performance check on a cheap phone and an older PC, security review of permissions, `docs/testing-guide.md`, a **scripted demo day** (seed + step-by-step walkthrough) the user can present to the bar owner. *Done when:* the demo script runs cleanly from a fresh clone.

## 15. Definition of done (overall)

- A shift can be closed in **under 10 minutes** by a worker with minimal training.
- The boss can see variance in **UGX** the same night and approve restocking from his phone.
- The worker site survives an internet outage mid-shift without data loss or duplication.
- Every stock shortage is traceable to a shift, a person and a time.
- Swahili and English work across both apps.
- All tests pass, all work is committed in clean history, and a fresh clone can be set up following the README alone.

---

**Begin now with Phase 0. Create the repository first, then build the skeletons, then stop and report using the format in Working Rule 3.**
