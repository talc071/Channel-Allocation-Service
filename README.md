# Channel Allocation Service

A small Python/FastAPI backend that manages channel identifiers `ono1`..`ono99999` and allocates them to ads across platforms (`fb`, `ob`, `snp`, `gtag`).

The full design is documented in [PLAN.md](PLAN.md).

## Quickstart

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# .\.venv\Scripts\activate.bat   # Windows cmd
# source .venv/bin/activate      # macOS/Linux

pip install -r requirements.txt
```

After activation, your prompt will show `(.venv)` and `uvicorn` / `pytest` will be on PATH.

### Run the API

With the venv activated:

```powershell
uvicorn main:app --reload
```

Or without activating (run uvicorn through the venv's Python):

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Or just run the module directly (it has an `if __name__ == "__main__"` block):

```powershell
.\.venv\Scripts\python.exe main.py
```

OpenAPI docs are served at `http://127.0.0.1:8000/docs`.

### Run the tests

```powershell
pytest                            # if venv is activated
.\.venv\Scripts\python.exe -m pytest   # otherwise
```

## API

| Method | Path | Body | Success |
| --- | --- | --- | --- |
| `POST` | `/allocations` | `{ad_id, platform}` | `201` `{ad_id, platform, channel, allocated_at}` |
| `POST` | `/allocations/free` | `{channel}` | `200` `{channel, freed_at, available_at}` |
| `POST` | `/allocations/cancel` | `{channel}` | `200` `{channel, ad_id, platform, canceled_at}` |
| `GET`  | `/allocations` | - | `200` list of active allocations |

Errors share a single envelope: `{error_code, message, details?}`.

## Domain rules

- Channel pool: `ono1`..`ono99999`.
- Allowed platforms: `fb`, `ob`, `snp`, `gtag`.
- A channel has at most one active allocation; an `(ad_id, platform)` pair has at most one active allocation.
- After `free`, the channel enters a 24-hour cooldown.
- An allocation can be canceled only within 5 minutes of `allocated_at` (inclusive). Cancel makes the channel reusable immediately.

## Design decisions

These are the "choose and document" items from the spec.

- **Duplicate active `(ad_id, platform)`** -> `409 duplicate_active_allocation` with the existing allocation in `details`. Clearer for clients than silently returning the same row.
- **Free on a non-active channel** -> `409 channel_not_active`. Explicit error is easier to debug than silent idempotent.
- **Cancel input shape** -> `channel` only (matches the Free input).
- **Channel selection** -> smallest available numeric `ono`. Deterministic, easy to test.
- **Storage** -> in-memory, behind `AllocationRepository`. Persistence is not required by the spec; swap in a SQL backend by replacing the repository.
- **Concurrency** -> a single `asyncio.Lock` in `AllocationService` guards every write. Prevents double allocation under normal concurrent use within one process.
- **Time** -> all timestamps are timezone-aware UTC.

## Project layout

```
main.py                  FastAPI app + DomainError -> HTTP handler
routes/                  HTTP endpoints
modules/                 Pydantic schemas (validation)
services/                Business rules (the only mutator)
repositories/            In-memory store
core/                    constants, clock, exceptions
tests/                   pytest + httpx + FixedClock
```

