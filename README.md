# Channel Allocation Service

A small fullstack project that manages channel identifiers `ono1`..`ono99999` and allocates them to ads across platforms (`fb`, `ob`, `snp`, `gtag`).

The project is split across two repos:

| Repo | Stack | Purpose |
| --- | --- | --- |
| **Channel-Allocation-Service** (backend) | Python 3.12 + FastAPI + Pydantic v2 | REST API, business rules, cooldown logic, tests |
| **Channel-Allocation-Service-UI** (frontend) | React 19 + Vite 6 + Tailwind v4 | UI for allocate / free / cancel and a live active table |

This README is shared by both repos so you only need one place to look. Backend-specific files referenced below live in the backend repo; frontend-specific files in the frontend repo.

The full backend design is documented in [PLAN.md](PLAN.md). AI usage is documented in [AI_USAGE.md](AI_USAGE.md).

---

## Setup and run

### Backend (one-command tests)

The backend ships with a one-command runner that creates a venv, installs dependencies, and runs `pytest`.

**Windows (PowerShell):**

```powershell
.\run_tests.ps1
```

**macOS / Linux:**

```bash
bash run_tests.sh
```

Either script is idempotent — re-running it just re-runs the tests. If PowerShell blocks the script with an execution-policy error, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Backend (start the API)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# .\.venv\Scripts\activate.bat   # Windows cmd
# source .venv/bin/activate      # macOS / Linux

pip install -r requirements.txt
uvicorn main:app --reload
```

OpenAPI docs are served at `http://127.0.0.1:8000/docs`. You can also run `python main.py` directly — `main.py` has an `if __name__ == "__main__"` block that starts uvicorn with reload.

### Frontend (start the UI)

Prerequisites: Node.js 18+ and npm. From the frontend repo:

```bash
npm install
npm run dev
```

The dev server runs at <http://localhost:5173>. By default Vite proxies any `/allocations*` request to `http://localhost:8000`, so just start the backend on port 8000 and the UI works.

To point at a different backend, set `VITE_API_BASE_URL` in `.env` (see `.env.example`):

```
VITE_API_BASE_URL=https://your-backend.example.com
```

When `VITE_API_BASE_URL` is set, the proxy is bypassed and requests go directly to that origin (CORS must be configured server-side).

---

## Test commands

| Repo | One command | Manual |
| --- | --- | --- |
| Backend | `.\run_tests.ps1` (Windows) / `bash run_tests.sh` (macOS/Linux) | `pytest` (with venv activated) |
| Frontend | `npm test` | `npm run test:watch` for watch mode |

Backend coverage today (33 tests): allocate / free / cancel happy paths, every error case in the API, advanced-cooldown unit tests including DST transitions and the midnight cliff, and concurrency stress tests proving no double-allocation under load.

Frontend coverage today: `validation.js` (ad id / platform / channel rules) and the `AllocatePanel` component (happy path, missing-field block, server-side 422 surfaced as a field error, with the API mocked).

---

## API

| Method | Path | Body | Success |
| --- | --- | --- | --- |
| `POST` | `/allocations` | `{ad_id, platform}` | `201` `{ad_id, platform, channel, allocated_at}` |
| `POST` | `/allocations/free` | `{channel}` | `200` `{channel, freed_at, available_at}` |
| `POST` | `/allocations/cancel` | `{channel}` | `200` `{channel, ad_id, platform, canceled_at}` |
| `GET`  | `/allocations` | - | `200` list of active allocations |

Errors share a single envelope: `{error_code, message, details?}`.

| HTTP | `error_code` | When |
| --- | --- | --- |
| `422` | (FastAPI default) | request body fails Pydantic validation (bad platform, bad channel format, empty `ad_id`) |
| `400` | `invalid_platform` | reserved for explicit platform errors |
| `404` | `allocation_not_found` | cancel target has no active row |
| `409` | `duplicate_active_allocation` | `(ad_id, platform)` is already active |
| `409` | `no_available_channels` | the entire pool is taken or in cooldown |
| `409` | `channel_not_active` | free called on a channel that has no active row |
| `409` | `cancel_window_expired` | cancel attempted more than 5 minutes after `allocated_at` |

---

## Domain rules

- Channel pool: `ono1`..`ono99999`.
- Allowed platforms: `fb`, `ob`, `snp`, `gtag`.
- A channel has at most one active allocation; an `(ad_id, platform)` pair has at most one active allocation.
- After `free`, the channel enters an **advanced cooldown** (see below).
- An allocation can be canceled only within 5 minutes of `allocated_at` (inclusive). Cancel makes the channel reusable immediately.

### Advanced cooldown (bonus)

`available_at` is the **next midnight in `America/New_York` that occurs strictly after `freed_at + 24h`**:

1. `T1 = freed_at + 24h`
2. Convert `T1` to `America/New_York` local time.
3. `available_at` = `00:00` on the day **after** `T1`'s NY date, in NY local time, returned in UTC.

Minimum cooldown is 24h, maximum is just under 48h, and releases bunch at NY midnight. DST is handled by `zoneinfo`. The pure helper lives in [core/cooldown.py](core/cooldown.py).

### Bonus items completed

- **Advanced cooldown** (NY midnight rule) — [core/cooldown.py](core/cooldown.py).
- **DST and midnight edge-case tests** — [tests/test_cooldown.py](tests/test_cooldown.py)
  - Spring forward and fall back, plus both ambiguous occurrences of 01:30 EDT/EST.
  - Midnight cliff: freed at `23:59` vs `00:01` NY-local — 2 minutes apart in `freed_at` produces a full 24h difference in `available_at`.
- **Stress / concurrency tests** — [tests/test_concurrency.py](tests/test_concurrency.py)
  - Pool of 1 + 10 concurrent allocate requests -> exactly 1 success, 9 fail with `no_available_channels`.
  - Pool of 50 + 50 concurrent requests -> all succeed with unique channels.
  - Pool of 5 + 20 concurrent requests -> 5 succeed, 15 fail cleanly.

---

## Design choices and trade-offs

### Backend

| Topic | Choice | Trade-off |
| --- | --- | --- |
| Web framework | **FastAPI** | Native Pydantic v2 integration and OpenAPI docs at `/docs`. Smaller and more typed than Flask. |
| Validation | **Pydantic v2** in `modules/` | Enforces the spec's exact shapes (`Platform` enum, `ono<n>` channel format, non-empty `ad_id`) at the boundary. Rest of the code can trust its inputs. |
| Storage | **In-memory** behind `AllocationRepository` | Simplest thing that works for a 3-4h scope. Loses data on restart and doesn't share across workers — see Next steps for the fix. |
| Concurrency | One global `asyncio.Lock` in `AllocationService` | Prevents double allocation in normal concurrent use within one process. Doesn't help across multiple uvicorn workers — would need DB constraints there. |
| Channel selection | Smallest available numeric `ono` | Deterministic, easy to test, predictable for debugging. Means lower indices wear in faster than high ones. |
| Cancel input | `channel` only | One key, matches Free, simpler frontend. Loses the ability to cancel by `(ad_id, platform)` without a lookup. |
| Duplicate active `(ad_id, platform)` | `409 duplicate_active_allocation` with the existing row in `details` | Clear failure for clients; alternative is silent idempotent which can hide bugs. |
| Free on a non-active channel | `409 channel_not_active` | Same reason — explicit error over silent success. |
| Time | All timestamps timezone-aware UTC | One source of truth; NY local time is only used inside the cooldown helper. |
| Clock | Injectable `Clock` / `FixedClock` | Tests are deterministic without sleeping or `freezegun`. |

### Frontend

| Topic | Choice | Trade-off |
| --- | --- | --- |
| Framework | **React 19 + Vite 6** (JavaScript) | Vite has near-instant dev reloads and minimal config; React covers forms + a small data table with no boilerplate. |
| Styling | **Tailwind CSS v4** | Utility classes keep the markup short and consistent without a separate CSS file per component. |
| Tests | **Vitest + React Testing Library** | Same runner Vite uses, jsdom out of the box, fast watch mode. |
| API wrapper | Single `src/api/client.js` with an `ApiError` class | Normalizes FastAPI's two error shapes (string `detail` and `[{loc, msg}]` 422 lists) into a flat `fieldErrors` map components can map to inline errors. |
| List state | `useAllocations` hook with `'idle' \| 'loading' \| 'ready' \| 'error'` and a request-id guard | Out-of-order responses can't overwrite newer data. |
| Refresh | Race-aware refresh on every successful action | Table always matches server state; no optimistic UI that can drift. |
| State management | None (props + one hook) | One screen with three forms doesn't justify Redux/Zustand. |

---

## Assumptions

- Single-process backend deployment (one uvicorn worker). Multi-worker would need persistent storage with `UNIQUE` indexes.
- Persistence is not required — the in-memory store is wiped on restart, and that's acceptable for the scope.
- `ad_id` is an opaque non-empty string; format isn't validated beyond non-empty/non-whitespace.
- The 5-minute cancel window is **inclusive** at exactly 5:00 (we use `>` not `>=`). Verified by `test_cancel_at_exactly_5_minutes_succeeds`.
- The advanced cooldown's "next midnight after T1" is **strict**: even if T1 lands exactly on NY midnight, we move to the following midnight. Verified by `test_freed_at_exactly_ny_midnight_skips_to_following_midnight` and the spring-forward midnight test.
- Canceled allocations release the channel immediately (no cooldown), per spec.
- The frontend assumes the API shapes documented above:
  - `AllocationResponse` = `{ ad_id, platform, channel, allocated_at }`.
  - `FreeResponse` = `{ channel, freed_at, available_at }`.
  - Channel format `^ono([1-9]\d{0,4})$` with index `<= 99999`.
- Cancel takes `{ channel }`. If the API ended up accepting `{ ad_id, platform }`, only `CancelPanel.jsx` needs to change — the API wrapper already forwards whichever keys are present.
- Backend and frontend are run side-by-side during development; the Vite proxy routes `/allocations*` to `localhost:8000` so no CORS configuration is needed locally.

---

## Project layout

### Backend

```
main.py                  FastAPI app + DomainError -> HTTP handler
routes/                  HTTP endpoints
modules/                 Pydantic schemas (validation)
services/                Business rules (the only mutator)
repositories/            In-memory store
core/                    constants, clock, exceptions, cooldown helper
tests/                   pytest + httpx + FixedClock + concurrency stress
run_tests.ps1            one-command test runner (Windows)
run_tests.sh             one-command test runner (macOS / Linux)
```

### Frontend

```
src/
  api/
    client.js            fetch wrapper, base URL, ApiError
    allocations.js       endpoint wrappers
  components/
    AllocatePanel.jsx    POST /allocations
    FreePanel.jsx        POST /allocations/free
    CancelPanel.jsx      POST /allocations/cancel
    AllocationsTable.jsx GET  /allocations
    Field.jsx            labeled input with a11y wiring
    PanelCard.jsx        consistent panel shell
    StatusBanner.jsx     success/error/info banner
    SubmitButton.jsx     primary button with pending state
  hooks/
    useAllocations.js    list state machine + race-safe refresh
    useAutoDismiss.js    auto-clear success banners
  utils/
    validation.js        ad_id / platform / channel rules
    format.js            date + platform formatting
  App.jsx                layout
  main.jsx               entry
  index.css              tailwind import
  test/setup.js          vitest setup
```

---

## What I would do next with more time

### Backend

- **Persist allocations** in SQLite or Postgres, with partial unique indexes on `(channel) WHERE status='active'` and on `(ad_id, platform) WHERE status='active'`. That makes the no-double-allocation guarantee survive restarts and multi-worker deployments.
- **Historical "as-of-time" query** by channel + timestamp (one of the spec's bonus items).
- **Pagination and filtering** for `GET /allocations` (e.g. by `platform`).
- **Structured logging** (request id, latency, outcome) and a `/healthz` endpoint.
- **Authentication** — at least an API key on the write endpoints.
- **Containerization** with a small `Dockerfile` and a `docker compose` setup for local dev with the future DB.
- **GitHub Actions CI** running `pytest` on every push and PR.
- **Property-based tests** (Hypothesis) for the cooldown helper around DST.

### Frontend

- More component coverage: `FreePanel`, `CancelPanel`, `AllocationsTable` loading/empty/error rendering, plus the `useAllocations` hook itself.
- Bonus historical "as-of-time" query UI by channel + timestamp.
- Toast system to replace inline banners when several actions succeed in quick succession.
- Optimistic UI for free/cancel with a rollback on server error.
- Polling or websocket-driven auto-refresh for the active table.
- Accessibility audit (focus traps, color contrast in dark mode, screen-reader pass on table semantics).
- Retry/backoff on transient 5xx in `client.js`.
- E2E tests with Playwright against a running backend.
