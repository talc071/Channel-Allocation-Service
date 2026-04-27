# Channel Allocation Service

A small Python / FastAPI backend that manages channel identifiers `ono1`..`ono99999` and allocates them to ads across platforms (`fb`, `ob`, `snp`, `gtag`).

The full design is documented in [PLAN.md](PLAN.md). AI usage is documented in [AI_USAGE.md](AI_USAGE.md).

---

## Run the tests in one command

The project ships with a one-command runner that creates a venv, installs dependencies, and runs `pytest`.

**Windows (PowerShell):**

```powershell
.\run_tests.ps1
```

**macOS / Linux:**

```bash
bash run_tests.sh
```

Either script is idempotent — re-running it just re-runs the tests.

If the PowerShell script is blocked by execution policy, run this once for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## Setup and run the API

If you also want to start the HTTP server:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# .\.venv\Scripts\activate.bat   # Windows cmd
# source .venv/bin/activate      # macOS / Linux

pip install -r requirements.txt
uvicorn main:app --reload
```

OpenAPI docs are served at `http://127.0.0.1:8000/docs`.

You can also run `python main.py` directly — `main.py` has an `if __name__ == "__main__"` block that starts uvicorn with reload.

### Test commands (manual)

```powershell
pytest                                   # if venv is activated
.\.venv\Scripts\python.exe -m pytest     # otherwise
```

---

## API

| Method | Path | Body | Success |
| --- | --- | --- | --- |
| `POST` | `/allocations` | `{ad_id, platform}` | `201` `{ad_id, platform, channel, allocated_at}` |
| `POST` | `/allocations/free` | `{channel}` | `200` `{channel, freed_at, available_at}` |
| `POST` | `/allocations/cancel` | `{channel}` | `200` `{channel, ad_id, platform, canceled_at}` |
| `GET`  | `/allocations` | - | `200` list of active allocations |

Errors share a single envelope: `{error_code, message, details?}`.

Error codes:

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

These are the "choose and document" items from the spec, plus other notable decisions.

| Topic | Choice | Trade-off |
| --- | --- | --- |
| Web framework | **FastAPI** | Native Pydantic v2 integration and OpenAPI docs at `/docs`. Smaller and more typed than Flask. |
| Validation | **Pydantic v2** in `modules/` | Enforces the spec's exact shapes (`Platform` enum, `ono<n>` channel format, non-empty `ad_id`) at the boundary. Rest of the code can trust its inputs. |
| Storage | **In-memory** behind `AllocationRepository` | Simplest thing that works for a 3-4h scope. Loses data on restart and doesn't share across workers — see Next steps for the fix. |
| Concurrency | One global `asyncio.Lock` in `AllocationService` | Prevents double allocation in normal concurrent use within one process. Doesn't help across multiple uvicorn workers — would need DB constraints there. |
| Channel selection | Smallest available numeric `ono` | Deterministic, easy to test, predictable for debugging. Means lower indices wear in faster than high ones. |
| Cancel input | `channel` only | One key, matches Free, simpler frontend. Loses the ability to cancel by `(ad_id, platform)` without a lookup. |
| Duplicate active `(ad_id, platform)` | `409 duplicate_active_allocation` with the existing row in `details` | Clear failure for clients; alternative is silent idempotent which can hide bugs. |
| Free on a non-active channel | `409 channel_not_active` | Same reason as above — explicit error over silent success. |
| Time | All timestamps timezone-aware UTC | One source of truth; NY local time is only used inside the cooldown helper. |
| Clock | Injectable `Clock` / `FixedClock` | Tests are deterministic without sleeping or `freezegun`. |

---

## Assumptions

- Single-process deployment (one uvicorn worker). Multi-worker would need persistent storage with `UNIQUE` indexes.
- Persistence is not required — the in-memory store is wiped on restart, and that's acceptable for the scope.
- `ad_id` is an opaque non-empty string; we don't validate format beyond non-empty/non-whitespace.
- The 5-minute cancel window is **inclusive** at exactly 5:00 (we use `>` not `>=`). Verified by `test_cancel_at_exactly_5_minutes_succeeds`.
- The advanced cooldown's "next midnight after T1" is **strict**: even if T1 lands exactly on NY midnight, we move to the following midnight. Verified by `test_freed_at_exactly_ny_midnight_skips_to_following_midnight` and the spring-forward midnight test.
- Canceled allocations release the channel immediately (no cooldown), per spec.
- Frontend is built in a separate repo and consumes this API.

---

## Project layout

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

---

## What I would do next with more time

- **Persist allocations** in SQLite or Postgres, with partial unique indexes on `(channel) WHERE status='active'` and on `(ad_id, platform) WHERE status='active'`. That makes the no-double-allocation guarantee survive restarts and multi-worker deployments.
- **Historical "as-of-time" query** by channel + timestamp (one of the spec's bonus items).
- **Pagination and filtering** for `GET /allocations` (e.g. by `platform`).
- **Structured logging** (request id, latency, outcome) and a `/healthz` endpoint.
- **Authentication** — at least an API key on the write endpoints.
- **Containerization** with a small `Dockerfile` and a `docker compose` setup for local dev with the future DB.
- **GitHub Actions CI** running `pytest` on every push and PR.
- **Frontend repo** wiring (separate repo per the spec) — React + Vite, with Allocate / Free / Cancel forms and a live Active table.
- **Property-based tests** (Hypothesis) for the cooldown helper around DST.
