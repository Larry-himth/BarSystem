# CLAUDE.md: BarSystem (bar POS and management system)

You are taking over day-to-day engineering on this repo from a previous AI agent that Larry can no longer use. Read this whole file first. It is the source of truth. `prompt.md` (the original spec Larry still has in the folder) is background only; where the two disagree, this file wins (see "Where prompt.md is outdated").

## 0. Who you work for and how

- Larry is a third-year Software Engineering student in Uganda building this for a real single bar. The owner ("the boss") is unavailable until December, when he expects a **working demo**. Larry must be able to explain and defend every part of this system, so explain the *why* of non-trivial code in a few lines, not just the what.
- Tone: direct and no-excuses. If Larry's thinking is shallow, emotional or vague, say so plainly and replace it with a better mental model. Push toward measurable progress: a passing check, a working screen, a merged PR.
- Design for Uganda's constraints: power cuts, unreliable internet, costly mobile data, cheap Android phones, no technical staff at the bar.
- Larry's machine: Arch Linux, Python 3.14 venv at `<repo>/.venv`, Flutter stable 3.47.x, Node (very new; use an LTS via nvm if native tooling breaks), test phone = Samsung S8 (Android 9, API 28).

## 1. Product in one paragraph

A single bar in Uganda. **Workers** use a web app (PWA) on a counter PC to sell, record deliveries/spillage/comps, count stock and close their shift. **The boss** uses an Android app (Flutter, delivered as an APK) to review shift reports, variances in UGX, cash and mobile-money totals, approve or dispute shifts and see stock. The point of the product is to attack three leaks: stock that disappears, cash/MoMo that does not match sales, and uncollected credit (tabs). Languages: English and Swahili (Luganda possible later). Money is whole UGX integers. Mobile money = customers pay the boss's personal number; there is **no MoMo API**: workers record the transaction reference and the boss confirms the total against his own phone.

## 2. Repo layout and how to run things

```
BarSystem/
  backend/      Django 5.2 + DRF + SimpleJWT + drf-spectacular (SQLite in dev, code must stay PostgreSQL-compatible)
    apps: users, catalog, stock, shifts, sales, tabs, audit, restock (stub), core
    config/ (settings.py, settings_test.py on branch phase-2g-fast-tests), scripts/ (verify.sh, simulate_day.py), tests/
  worker-web/   React + Vite 5 + TypeScript PWA (skeleton + axios client only so far)
  boss-app/     Flutter app (hello-world health check works on the S8)
  docs/         architecture/api/testing stubs
```

```bash
cd backend && source ../.venv/bin/activate
python -m pytest -q                       # full suite
bash scripts/verify.sh                    # the definition-of-done check (see section 5)
rm db.sqlite3 && python manage.py migrate -v0 && python manage.py seed_demo
python manage.py runserver 0.0.0.0:8000   # needs ALLOWED_HOSTS in backend/.env (comma list, NO spaces, include the LAN IP from `hostname -I`)
```

Seed users: `owner`/1234, `manager`/2222, `b1`/1111, `b2`/3333. `backend/.env` is git-ignored; **never put a real secret in `.env.example`** (a real key was once put there; treat it as burned). The app server must be restarted after `.env` edits.

## 3. What is built (backend, phases 0 to 2f merged; tag `v0.2-phase2` = merge commit d4d22de)

**Ledger (core principle).** Stock is never an editable number. `StockMovement` rows are immutable: `save`/`delete` blocked, queryset `update()`/`delete()` raise, every FK on financial/ledger data is `on_delete=PROTECT`, admin is read-only. Quantities are **integers in the smallest base unit** (beer/soda = pieces; spirits = ml, so a 750 ml bottle = 750 and a 25 ml tot = 25). Types: OPENING, SALE, DELIVERY, SPILLAGE, COMP, ADJUSTMENT, VOID_REVERSAL. Current stock = sum of movements (`stock/services.py::current_stock`). Rule: after go-live, no migration may delete or rewrite `StockMovement` or `AuditLog` rows. (Migration `stock/0004` deleted legacy CLOSING_COUNT rows through the historical model; acceptable only because nothing was live.)

**Count model (phase 2f).** A count is an observation, not a stock change. `StockCount(shift, item, kind OPENING|CLOSING, counted_qty, expected_qty, counted_by, created_at)`, unique per (shift, item, kind). Counts **never create StockMovement rows**. `expected_qty` is stored server-side and never serialized to a BARTENDER (blind count). On shift **approval**, one `ADJUSTMENT` per item with a closing count is written = closing count minus the ledger balance as of the shift's `closed_at`, `created_by` = approving manager, zero deltas skipped, approving twice returns 400 and writes nothing more; dispute writes no adjustment.

**Auth.** `POST /api/v1/auth/login/` with `{username, pin}` returns `{access, refresh}` (access lifetime currently 5 minutes). PINs are hashed (`check_password`; the plaintext fallback was removed). 5 wrong PINs lock an account for 15 minutes (`users/utils.py`: `verify_pin`, `record_pin_failure`; fields `pin_failed_attempts`, `pin_locked_until`). Login ignores invalid Authorization headers. Roles: OWNER, MANAGER, BARTENDER. `GET/PATCH /api/v1/auth/me/` (PATCH accepts only `language`: `en|sw`; anything else returns `INVALID_FIELDS`).

**Sales.** `POST /api/v1/sales/` `{shift_id, lines:[{item_unit_id, qty}], payments:[{method CASH|MOMO|TAB, amount, momo_ref?}], client_uuid?}`. Prices come from `ItemUnit.sell_price` on the server; the client cannot set them. Payments must sum exactly to the total (`PAYMENT_MISMATCH`). `client_uuid` makes creation idempotent. Selling below zero stock is allowed but sets `negative_stock_flag` and writes an audit row. Zero/negative quantities and sales on non-OPEN shifts are rejected (`SHIFT_NOT_OPEN`).
**Void:** `POST /api/v1/sales/{id}/void/` with `reason` plus either (a) the caller is MANAGER/OWNER and sends `pin`, or (b) the caller is anyone with a session and sends `approver_username` + `approver_pin` (approver must be a different MANAGER/OWNER). Reversals are `VOID_REVERSAL` movements with `created_by` = caller; the approver is recorded in the `VOID_OVERRIDE` audit row (`approver_id`). Voiding twice returns `ALREADY_VOIDED`.

**Shifts.** A database partial unique constraint allows only one OPEN shift. Endpoints under `/api/v1/shifts/`: `open/`, `<id>/count/`, `<id>/close/`, `<id>/submit/`, `<id>/approve/`, `<id>/dispute/`, `<id>/momo-confirm/`, plus read APIs `GET /shifts/` and `GET /shifts/<id>/report/` (MANAGER/OWNER only). The report returns per-item opening, deliveries, sales, voids, spillage, comps, expected, counted, variance and `variance_ugx`; expected cash and expected MoMo (voided sales excluded) with the MoMo reference list; spillage/comp/void totals per user. Submitted shifts lock (writes rejected with `SHIFT_NOT_OPEN`); counts on a locked shift are rejected; close requires a count for every active item with no duplicates. `stock/services` + `shifts/services.py` hold the arithmetic; `scripts/simulate_day.py` simulates a day.

**Other:** `POST /stock-movements/` (DELIVERY, SPILLAGE, COMP; ADJUSTMENT manager-only; reasons required for losses), `/tabs/` record and repay, `AuditLog` (append-only) for login, shift open, sale create, void, counts, submit, stock actions.

**Tests:** about 70 pytest tests with exact-value assertions. Security rules were mutation-tested (break the rule on purpose, see the test fail, restore).

## 4. In flight right now (unmerged branches, all pushed or local)

- `phase-2g-read-api` (eec3eb6, rebased off `77e9b95`): `GET /api/v1/items/` (any authenticated user; **explicit allow-list serializers**: BARTENDER keys exactly `{id, name_en, name_sw, category, icon, units}`, units `{id, label_en, label_sw, qty_in_base_unit, sell_price, can_sell, can_buy}`; MANAGER/OWNER additionally `buy_price`, `par_level`; bartenders never see cost or any quantity), `GET /api/v1/stock/` (MANAGER/OWNER; `item_id, name_en, name_sw, stock_base, par_level, is_low, base_unit`), `ItemUnit.label_sw` with fallback to `label`.
- `phase-2g-fast-tests` (9208a0d, branched from `77e9b95`, **not yet rebased onto read-api**): `config/settings_test.py` with an MD5 hasher for tests only, `pytest.ini` points at it, a guard test fails if the production settings ever contain md5/plaintext hashers. Suite: ~12 s instead of ~5 min.
- `boss-app-hello` (2f33aed, pushed): Flutter screen that calls `<server>/api/v1/health/` and shows `200`. Android manifest has INTERNET permission and `usesCleartextTraffic="true"` (dev only).
- `backup-2g-before-rebase` is a local safety branch; ignore it.
- Larry has **not yet** run: rebasing fast-tests onto read-api, the guard mutation test, the PR/merge, the post-merge verify, and the 2g-contract task below.

## 5. Working rules (non-negotiable)

Git:
1. Never commit to `main`. One branch per task (`phase-2g-contract`, ...). **Never push, merge, tag, force-push, reset --hard, clean, or `git checkout -- <paths>` unless Larry explicitly asks in that message.** (Larry once lost uncommitted work to a blanket checkout.) Larry pushes and merges PRs himself after verifying. you can give him the commands to do so.
2. Commit at the end of every task with a Conventional Commit message and show the diff stat. Uncommitted work is not done.
3. Do not edit by line number when other changes may exist; match on strings. Never touch `worker-web/` or `boss-app/` inside a backend branch (and vice versa).

Verification:
4. Start every reply with `git branch --show-current`.
5. "Done" means `bash backend/scripts/verify.sh` prints no uncommitted files, `none` for the loose-assertion and plaintext-PIN checks, no `MISSING`, and a real `N passed` line. Paste the raw output. You may append new checks to `verify.sh` only when asked; never weaken it.
6. Tests assert **exact values and exact error `code`s**, not status ranges (`in (400, 403)` is banned) and not field existence. Never delete or loosen an assertion; if one must change, list it explicitly with the reason.
7. For any security or ledger rule you add or touch, run a **mutation test**: break the rule on purpose with a string-based `sed` on a copy, show the test failing, restore the file from the copy, and show `git status` clean.
8. If something fails or cannot run, say so. Never claim a test passed that you did not run. Never "fix" a failing test by bending application behavior without saying so.

Security and design invariants (do not relitigate):
9. The server computes prices, totals, expected stock, variances and cash. Never trust client-supplied values for these.
10. Bartenders never receive cost prices, expected quantities, variances or stock quantities. Use explicit allow-list serializers, not field popping.
11. Role checks happen server-side on every endpoint. Failures return `{"code": "...", "message": "..."}` with a stable machine code; the apps translate by code, never by displaying the server message.
12. Every state-changing action writes an `AuditLog` row. Never log PINs.
13. Locked (submitted/approved) shifts reject changes. Ledger rows are never updated or deleted.
14. Keep code PostgreSQL-compatible. Wrap idempotent creates so the `IntegrityError` handler sits outside the inner `transaction.atomic()` block.

Process:
15. One task at a time, then stop and report. No scope creep: anything not in the task list goes under "later". Ask Larry before architectural changes.

## 6. Decisions already made (do not reopen without a failure you can name)

- Worker side stays a **PWA** (not a desktop app). Boss side is **Flutter** (not React Native), APK for testing/delivery.
- Backend will be **hosted on a VPS** behind HTTPS with a domain (service workers and Android release builds require HTTPS), PostgreSQL, gunicorn, Caddy; nightly `pg_dump` copied off-server. Not deployed yet; Larry has not confirmed a payment method or provider.
- **Offline-first for sales only** in the December demo: the sell screen writes locally first (IndexedDB outbox with client-generated UUIDs) and syncs later. Counting, closing and approvals may require a connection.
- Workers switch language themselves (login screen and header); `User.language` is the default; translate by error code; item names come from the API.
- Allow selling into negative stock but flag it. Payments must match totals exactly. No MoMo API. One boss; a single bar.

## 7. Known issues and debt (fix in the order Larry approves)

1. Voids are allowed on SUBMITTED/APPROVED shifts, which rewrites reviewed numbers. Allow voids only while the sale's shift is OPEN; later corrections are manager ADJUSTMENTs.
2. Voiding a TAB sale does not restore the tab balance.
3. `ALREADY_VOIDED` is checked after PIN verification (can burn lockout attempts): check it first.
4. Wrong **approver** PINs count against the approver, so a worker can lock the manager out. Count failed approver attempts against the caller's override attempts instead.
5. `variance_value` uses `buy_price or 0`; it should fall back to the sell price when buy price is missing.
6. Three overlapping end-of-shift endpoints (`count`, `close`, `submit`): document the exact call order and propose which one(s) the apps use; Larry decides.
7. Denied actions (denied void, PIN lockout, failed login) leave no audit trail. Add rows without storing the attempted PIN.
8. JWT access lifetime (5 min) must come from an env setting; the PWA must refresh silently so workers are never logged out mid-sale.
9. Confirm `close` requires a count for **every Item with `is_active=True`** (not only items that had movements this shift).
10. Dev `SECRET_KEY` warning (key under 32 bytes): use a strong key in `backend/.env`.
11. Swahili strings seeded by the previous agent are unreviewed; a native speaker must review before the demo. Unknown translations should stay blank and fall back to English.
12. Open question for Larry: may a new shift open while the previous one awaits review? Recommended: yes; compare the next opening count against the previous *closing count*, not a ledger that has not absorbed the boss's adjustment yet.

## 8. Task queue (do in order; stop after each)

**T0. Orientation (no changes).** Read this file and `prompt.md`. Run `git status`, `git log --oneline --all --graph -15`, `bash backend/scripts/verify.sh`. Reply with: a summary in at most 10 lines, the baseline pass count and runtime, any contradictions between this file and the code or `prompt.md`, and any claim here you could not verify. Change nothing.

**T1. Land 2g.** On `phase-2g-fast-tests`, rebase onto `phase-2g-read-api` (stash Larry's unrelated `boss-app/pubspec.lock` change first; abort and report on conflict). Run verify (expect 73 passed, under a minute), run the guard mutation test (append an MD5 `PASSWORD_HASHERS` to `config/settings.py`, expect the guard test to fail, restore), confirm no `DJANGO_SETTINGS_MODULE` points at `config.settings_test` outside `pytest.ini`. Read the Swahili strings in the seed diff and list any you are not certain about. Stop and tell Larry the branch is ready for his PR.

**T2. 2g-contract** (new branch `phase-2g-contract` from updated `main`, after Larry merges T1). (1) `GET /api/v1/shifts/current/` for any authenticated user: `{id, status, opened_by_username, opened_at}` for the single OPEN shift or `{"shift": null}`. (2) `GET /api/v1/sales/?shift_id=N`: a BARTENDER may list only the currently OPEN shift's sales (anything else `403 FORBIDDEN`); MANAGER/OWNER any shift; rows `id, total, created_at, created_by_username, is_voided, lines (unit label en/sw, qty, unit_price), payments (method, amount, momo_ref)`, newest first, max 200. (3) Export `docs/openapi.yaml` (`python manage.py spectacular --file docs/openapi.yaml`) plus a test that fails when the committed file is stale. (4) `docs/api.md`: every endpoint with method, path, roles, request, response, every error `code` with status and trigger, the allowed `reason` values, and the exact call order of a full shift (open, sell, count, close, submit, approve) with a recommendation on the overlapping end-of-shift endpoints. (5) A test that scans `"code": "..."` literals in all `views.py` files and fails if any is missing from `docs/api.md`. Exact-value tests for (1) and (2), including a bartender requesting a closed shift's sales and a voided sale's `is_voided`. Target: contract frozen by Nov 7.

**T3. Hardening (2g-2).** Debt items 1 to 5, 7, 8, 9, 10 above, one commit each with its mutation test. Update `docs/api.md` for any code you add.

**T4. Worker PWA v1** (`worker-web/`, TypeScript). Generate API types from `docs/openapi.yaml`. Pin dependency versions. Screens: PIN login (large numeric keypad, language switcher visible before login), open/continue shift, sell (picture/icon grid, unit choice, cart, Cash/MoMo/Tab, change calculator), stock-in, loss/comp with reason codes, count (blind at close), close shift with cash declaration, tabs, sync status and a visible "needs attention" list. **Local-first sell**: IndexedDB (Dexie) outbox keyed by client UUID, idempotent retry, clear online/offline and unsynced-count indicator; silent token refresh; `vite-plugin-pwa`. i18n with `i18next`: `en.json` and `sw.json`, zero hardcoded strings, error text keyed by error code, and a test that fails when a key exists in one file but not the other. Works well with a mouse on a PC monitor. Browser-test against the real backend; report what you could not test.

**T5. Flutter boss app** (`boss-app/`, from the `boss-app-hello` base). Login with an **editable server address** and `flutter_secure_storage`; `flutter_localizations` + ARB files (en, sw) from the first screen; shift list (submitted first), shift report (variance in red, cash and MoMo expected vs declared, voids/comps/spillage per user), MoMo confirm/dispute, approve/dispute with a note, stock with low-stock highlight; 60-second polling for alerts (push is later). Keep it thin: no business logic. Move `usesCleartextTraffic` into the debug manifest only; release builds stay HTTPS-only. Produce `flutter build apk --release` and give Larry install steps. Test on the S8 over the LAN, then against the VPS.

**T6. Staging on the VPS** (only when Larry has chosen a provider and domain): run the full suite against PostgreSQL first; Caddy + gunicorn + systemd; `DEBUG=False`, secrets via env; firewall 22/80/443; nightly `pg_dump` to an off-server copy and one restore test; update the apps' server address.

**Later (do not build before the demo):** restock proposals, tab aging reports, FCM push and SMS alerts, receipt printing, multi-branch, MoMo API.

## 9. Where prompt.md is outdated

React Native became Flutter; counts no longer create stock movements (see the count model); the void flow uses an approver override; `/stock/` and `/items/` exist with allow-list serializers; payments must match totals exactly; tests run with a fast hasher; the phase plan was split into 2a to 2g; deployment is a VPS. The original build-phase list is superseded by section 8.
