# Bar POS API

Base URL: `/api/v1/`.

Authentication uses a Bearer JWT access token:

```http
Authorization: Bearer <access>
```

Roles are `OWNER`, `MANAGER` and `BARTENDER`. Unless an endpoint says otherwise, authentication is required. Errors use `{"code": "...", "message": "..."}`; validation failures use normal DRF field errors and HTTP 400.

OpenAPI schema: `/api/schema/`. Swagger UI: `/api/docs/`.

## Endpoint index

| Method | Path | Allowed roles |
|---|---|---|
| GET | `/api/v1/health/` | Public |
| POST | `/api/v1/auth/login/` | Public |
| GET | `/api/v1/auth/me/` | Any authenticated |
| PATCH | `/api/v1/auth/me/` | Any authenticated |
| GET | `/api/v1/items/` | Any authenticated |
| GET | `/api/v1/stock/` | `MANAGER`, `OWNER` |
| POST | `/api/v1/stock-movements/` | Any authenticated; `ADJUSTMENT` is `MANAGER`/`OWNER` only |
| GET | `/api/v1/shifts/` | `MANAGER`, `OWNER` |
| POST | `/api/v1/shifts/open/` | Any authenticated |
| GET | `/api/v1/shifts/current/` | Any authenticated |
| POST | `/api/v1/shifts/{id}/count/` | Any authenticated |
| POST | `/api/v1/shifts/{id}/submit/` | Any authenticated |
| POST | `/api/v1/shifts/{id}/close/` | Any authenticated |
| POST | `/api/v1/shifts/{id}/approve/` | `MANAGER`, `OWNER` |
| POST | `/api/v1/shifts/{id}/dispute/` | `MANAGER`, `OWNER` |
| POST | `/api/v1/shifts/{id}/momo-confirm/` | `MANAGER`, `OWNER` |
| GET | `/api/v1/shifts/{id}/report/` | `MANAGER`, `OWNER` |
| POST | `/api/v1/sales/` | Any authenticated |
| GET | `/api/v1/sales/?shift_id={id}` | Any authenticated; bartenders only for the open shift |
| POST | `/api/v1/sales/{id}/void/` | Any authenticated; see approval rule below |
| POST | `/api/v1/tabs/` | Any authenticated |
| POST | `/api/v1/tabs/{id}/payments/` | Any authenticated |
| GET | `/api/schema/` | Public |
| GET | `/api/docs/` | Public |

## Health

### GET `/api/v1/health/`

- Roles: public.
- Request body: none.
- Success `200`: `{"status": "ok", "service": "bar-pos-api"}`.
- Errors: none.

## Authentication

### POST `/api/v1/auth/login/`

- Roles: public.
- Request body: `{"username": "b1", "pin": "1111"}`.
- Success `200`: `{"access": "<jwt>", "refresh": "<jwt>"}`.
- Errors:
  - `AUTH_FAILED` `401`: username is missing, inactive or unknown, or the PIN is wrong.
  - `400`: missing/invalid serializer fields.

### GET `/api/v1/auth/me/`

- Roles: any authenticated user.
- Request body: none.
- Success `200`: `{"id": 1, "username": "b1", "role": "BARTENDER", "language": "en"}`.
- Errors: `401` when unauthenticated.

### PATCH `/api/v1/auth/me/`

- Roles: any authenticated user.
- Request body: `{"language": "en"}` or `{"language": "sw"}`. These are the only allowed fields.
- Success `200`: `{"id": 1, "username": "b1", "role": "BARTENDER", "language": "sw"}`.
- Errors:
  - `INVALID_FIELDS` `400`: any key other than `language` is present, including attempts to change `role`, `username` or a PIN.
  - `INVALID_LANGUAGE` `400`: `language` is not exactly `en` or `sw`.
  - `401` when unauthenticated.

## Catalog

### GET `/api/v1/items/`

- Roles: any authenticated user.
- Request body: none.
- Success `200`: a JSON array of active items, ordered by `category`, `name_en`, then `id`.
  - `BARTENDER` item keys are exactly `id`, `name_en`, `name_sw`, `category`, `icon`, `units`.
  - `MANAGER`/`OWNER` item keys are the bartender keys plus `buy_price` and `par_level`.
  - Each unit has exactly `id`, `label_en`, `label_sw`, `qty_in_base_unit`, `sell_price`, `can_sell`, `can_buy`.
  - `label_en` is the stored `label`; `label_sw` is the stored Swahili label, falling back to `label` when blank.
- Errors: `401` when unauthenticated.

## Stock

### GET `/api/v1/stock/`

- Roles: `MANAGER`, `OWNER`.
- Request body: none.
- Success `200`: one row per active item:
  `{"item_id": 1, "name_en": "Nile Special", "name_sw": "Nile Special", "base_unit": "bottle", "stock_base": 24, "par_level": 24, "is_low": false}`.
  `is_low` is true when `stock_base < par_level`.
- Errors:
  - `FORBIDDEN` `403`: caller is not `MANAGER`/`OWNER`.
  - `401` when unauthenticated.

### POST `/api/v1/stock-movements/`

- Roles: any authenticated user for `DELIVERY`, `SPILLAGE`, `COMP`; only `MANAGER`/`OWNER` for `ADJUSTMENT`.
- Request body:
  ```json
  {
    "item_id": 1,
    "shift_id": 1,
    "type": "DELIVERY",
    "qty_base": 12,
    "reason": ""
  }
  ```
  `type` is one of `DELIVERY`, `SPILLAGE`, `COMP`, `ADJUSTMENT`. `qty_base` is signed in the request; `SPILLAGE` and `COMP` are stored as negative movements. `reason` is required and non-empty for `SPILLAGE` and `COMP`.
- Success `201`: `{"status": "created"}`.
- Errors:
  - `FORBIDDEN` `403`: a bartender tries to create an `ADJUSTMENT`.
  - `SHIFT_NOT_OPEN` `400`: the supplied shift is not `OPEN`.
  - `400`: invalid type, zero quantity, missing reason for spillage/comp, or unknown item/shift.
- Allowed `reason` values: `reason` is free-form text. Clients should use these reason codes:
  - `SPILLAGE`: `BROKEN`, `SPILLED`, `EXPIRED`.
  - `COMP`: `STAFF_MEAL`, `PROMOTION`, `OWNER_APPROVED`.
  - `ADJUSTMENT`: `STOCK_TAKE`, `COUNT_RECONCILIATION`, `CORRECTION`.

## Shifts

### GET `/api/v1/shifts/`

- Roles: `MANAGER`, `OWNER`.
- Query parameters: `status`, `date` (`YYYY-MM-DD`), `start_date`, `end_date`.
- Request body: none.
- Success `200`: newest-first shift summaries.
- Errors:
  - `FORBIDDEN` `403`: caller is not `MANAGER`/`OWNER`.
  - `401` when unauthenticated.

### POST `/api/v1/shifts/open/`

- Roles: any authenticated user.
- Request body: `{"notes": ""}`; `notes` is optional.
- Success `201`: `{"id": 1, "status": "OPEN", "code": "SHIFT_OPENED"}`.
- Errors:
  - `SHIFT_OPEN_EXISTS` `400`: an `OPEN` shift already exists.
  - `401` when unauthenticated.

### GET `/api/v1/shifts/current/`

- Roles: any authenticated user.
- Request body: none.
- Success `200` with the single open shift:
  `{"id": 1, "status": "OPEN", "opened_by_username": "b1", "opened_at": "2026-01-01T10:00:00Z"}`.
  If no shift is open, success `200` is `{"shift": null}`.
- Errors: `401` when unauthenticated.

### POST `/api/v1/shifts/{id}/count/`

- Roles: any authenticated user.
- Request body:
  ```json
  {
    "type": "OPENING",
    "counts": [{"item_id": 1, "counted_qty": 24}]
  }
  ```
  `type` is `OPENING` or `CLOSING`.
- Success `201`: `{"status": "recorded"}`. For non-bartenders it also includes `variances`; bartender responses omit expected quantities and variances.
- Errors:
  - `SHIFT_NOT_OPEN` `400`: shift is not `OPEN`.
  - `400`: invalid type/counts or unknown item.
  - `404`: shift not found.

### POST `/api/v1/shifts/{id}/submit/`

- Roles: any authenticated user.
- Request body:
  ```json
  {
    "counts": [{"item_id": 1, "counted_qty": 24}],
    "pin": "",
    "declared_cash": 0
  }
  ```
  `counts` must contain every active item exactly once. `pin` and `declared_cash` are optional.
- Success `200`: `{"status": "submitted", "code": "SHIFT_SUBMITTED", "items": [...]}`.
- Errors:
  - `SHIFT_NOT_OPEN` `400`: shift is not `OPEN`.
  - `COUNT_INCOMPLETE` `400`: any active item is missing, duplicated or unexpected.
  - `400`: invalid counts.
  - `404`: shift not found.

### POST `/api/v1/shifts/{id}/close/`

- Roles: any authenticated user.
- Request body and validation: identical to `submit`.
- Success `200`: `{"status": "submitted", "code": "SHIFT_CLOSED", "items": [...]}`.
- Errors:
  - `SHIFT_NOT_OPEN` `400`: shift is not `OPEN`.
  - `COUNT_INCOMPLETE` `400`: any active item is missing, duplicated or unexpected.
  - `400`: invalid counts.
  - `404`: shift not found.

### POST `/api/v1/shifts/{id}/approve/`

- Roles: `MANAGER`, `OWNER`.
- Request body: none.
- Success `200`: `{"status": "approved", "code": "SHIFT_APPROVED"}`. Approval writes reconciliation `ADJUSTMENT` movements when closing counts differ from the ledger.
- Errors:
  - `FORBIDDEN` `403`: caller is not `MANAGER`/`OWNER`.
  - `SHIFT_ALREADY_APPROVED` `400`: the shift is already approved, or its reconciliation adjustment already exists.
  - `404`: shift not found.

### POST `/api/v1/shifts/{id}/dispute/`

- Roles: `MANAGER`, `OWNER`.
- Request body: `{"note": "Reason for dispute"}`.
- Success `200`: `{"status": "disputed", "code": "SHIFT_DISPUTED"}`.
- Errors:
  - `FORBIDDEN` `403`: caller is not `MANAGER`/`OWNER`.
  - `400`: missing note.
  - `404`: shift not found.

### POST `/api/v1/shifts/{id}/momo-confirm/`

- Roles: `MANAGER`, `OWNER`.
- Request body: `{"status": "CONFIRMED", "note": ""}`. `status` is `PENDING`, `CONFIRMED` or `DISPUTED`; `note` is optional.
- Success `200`: `{"status": "confirmed", "code": "MOMO_CONFIRMED"}`.
- Errors:
  - `FORBIDDEN` `403`: caller is not `MANAGER`/`OWNER`.
  - `400`: invalid status.
  - `404`: shift not found.

### GET `/api/v1/shifts/{id}/report/`

- Roles: `MANAGER`, `OWNER`.
- Request body: none.
- Success `200`: report with `id`, `status`, per-item expected/counted/variance data, `expected_cash`, `declared_cash`, `expected_momo`, `momo_refs` and per-user totals.
- Errors:
  - `FORBIDDEN` `403`: caller is not `MANAGER`/`OWNER`.
  - `404`: shift not found.

## Sales

### POST `/api/v1/sales/`

- Roles: any authenticated user.
- Request body:
  ```json
  {
    "client_uuid": "optional-uuid",
    "shift_id": 1,
    "lines": [{"item_unit_id": 1, "qty": 1}],
    "payments": [{"method": "CASH", "amount": 3000, "momo_ref": ""}]
  }
  ```
  `method` is `CASH`, `MOMO` or `TAB`. `momo_ref` is required for `MOMO`; `tab_id` is required for `TAB`. Repeating a `client_uuid` returns the original sale.
- Success `201`: `{"id": 1, "total": 3000, "negative_stock_flag": false}`.
- Errors:
  - `SHIFT_NOT_OPEN` `400`: shift is not `OPEN`.
  - `PAYMENT_MISMATCH` `400`: payment amounts do not sum to the computed sale total.
  - `400`: missing lines/payments, invalid quantity, missing MoMo reference or tab, or unknown unit/tab.
  - `404`: shift not found.

### GET `/api/v1/sales/?shift_id={id}`

- Roles: any authenticated user.
- Bartenders: only the currently `OPEN` shift’s sales. A closed/submitted/approved/disputed shift returns `FORBIDDEN` `403`.
- `MANAGER`/`OWNER`: any shift.
- Request body: none. `shift_id` is required and must be an integer.
- Success `200`: newest first, at most 200 rows. Each row has exactly `id`, `total`, `created_at`, `created_by_username`, `is_voided`, `lines`, `payments`.
  - Each line has exactly `label_en`, `label_sw`, `qty`, `unit_price`; `label_sw` falls back to `label_en` when blank.
  - Each payment has exactly `method`, `amount`, `momo_ref`.
  - `is_voided` is true when `voided_at` is set.
- Errors:
  - `FORBIDDEN` `403`: a bartender requests any shift that is not open.
  - `INVALID_SHIFT_ID` `400`: `shift_id` is missing or is not an integer.
  - `404`: shift not found.
  - `401` when unauthenticated.

### POST `/api/v1/sales/{id}/void/`

- Roles: any authenticated user, subject to approval:
  - `MANAGER`/`OWNER` callers may void with their own `pin`.
  - A bartender must provide `approver_username` and `approver_pin` for an active `MANAGER`/`OWNER`; the approver must differ from the caller.
- Request body:
  ```json
  {
    "reason": "Wrong item",
    "pin": "9999",
    "approver_username": "",
    "approver_pin": ""
  }
  ```
  `reason` is required. Use either `pin` (manager/owner caller) or both approver fields (bartender override).
- Success `200`: `{"status": "voided", "override": false}`. Voiding writes reversing `VOID_REVERSAL` movements and preserves the sale.
- Errors:
  - `APPROVER_INVALID` `403`: approver username is unknown or inactive.
  - `APPROVER_SAME_AS_CALLER` `403`: approver is the caller.
  - `APPROVER_NOT_AUTHORIZED` `403`: approver is not `MANAGER`/`OWNER`.
  - `INVALID_PIN` `403`: caller or approver PIN is wrong.
  - `PIN_LOCKED` `403`: PIN verification is temporarily locked after failed attempts.
  - `FORBIDDEN` `403`: a bartender attempts a void without approver credentials.
  - `ALREADY_VOIDED` `400`: the sale was already voided.
  - `400`: missing reason or invalid request fields.
  - `404`: sale not found.

## Tabs

### POST `/api/v1/tabs/`

- Roles: any authenticated user.
- Request body: `{"customer_name": "John", "phone": ""}`; `phone` is optional.
- Success `201`: `{"id": 1, "code": "TAB_CREATED"}`.
- Errors: `400` for missing customer name; `401` when unauthenticated.

### POST `/api/v1/tabs/{id}/payments/`

- Roles: any authenticated user.
- Request body: `{"amount": 5000, "method": "CASH"}`. `method` is `CASH` or `MOMO`.
- Success `200`: `{"status": "recorded", "code": "TAB_PAYMENT_RECORDED"}`.
- Errors:
  - `NO_SHIFT` `400`: no shift exists at all to attach the repayment to.
  - `400`: invalid amount/method.
  - `404`: tab not found.

## OpenAPI

### GET `/api/schema/`

- Roles: public.
- Request body: none.
- Success `200`: generated OpenAPI document.
- Errors: none.

### GET `/api/docs/`

- Roles: public.
- Request body: none.
- Success `200`: Swagger UI.
- Errors: none.

## Full shift call order

The contract order is `open → sell → count → close → submit → approve`. Because `close` and `submit` overlap, the executable sequence is:

1. `POST /api/v1/shifts/open/`
2. `POST /api/v1/sales/` for each sale.
3. `POST /api/v1/shifts/{id}/count/` for opening counts and any intermediate closing count.
4. `POST /api/v1/shifts/{id}/submit/` (or, only as a compatibility alias, `POST /api/v1/shifts/{id}/close/`).
5. `POST /api/v1/shifts/{id}/approve/`

`count`, `close` and `submit` overlap:

- `count` records a partial or complete set of counts and keeps the shift `OPEN`.
- `close` and `submit` are aliases: both require the complete closing count, write `CLOSING` `StockCount` rows, set the shift to `SUBMITTED`, and return the same item variance payload. Only the success `code` and audit action differ (`SHIFT_CLOSED` vs `SHIFT_SUBMITTED`).
- Never call both `close` and `submit`: the first call changes the status away from `OPEN`, so the second returns `SHIFT_NOT_OPEN`.
- Apps should use `POST /api/v1/shifts/{id}/submit/`. `/close/` is retained for compatibility; `/count/` is for opening or intermediate counts, not as a replacement for the final submit.
