# AI Usage

## Tool

Cursor IDE with Claude. I worked with it the same way I'd work with a more senior teammate — explain what I want, review what they suggest, push back when something feels off.

## How I worked

- I started by saving the full assignment as `instructions.txt` so the AI always had the spec in front of it.
- Switched Cursor into **Plan mode** first. In this mode the AI can only read and propose, not edit. I had it read the spec carefully and produce a detailed plan: folder layout, every Pydantic schema, the contract of each service method, status codes, tests. I reviewed it, answered a couple of clarifying questions (e.g. storage choice), and only then approved.
- Switched to **Agent mode** to actually build the backend, one todo at a time, following the plan.
- Switched to **Ask mode** whenever I wanted to understand something without risking edits — "what does `create_app` actually do?", "where is concurrency handled?", "what error does cancel-after-5-minutes return?". Read-only, no surprises.
- After the backend was solid, I built the frontend in React + Vite the same way: Plan -> Agent -> Ask, and wired it to the API endpoints.
- I switched modes a lot. Plan when I needed to think, Agent when I knew what to do, Ask when I just wanted to learn.

## Decisions I made

- **FastAPI** for the backend. The assignment is small and the API surface is tiny, and FastAPI gives me request validation, OpenAPI docs at `/docs`, and async support for free. Less code than Flask + manual validation.
- **Pydantic** for every request and response. The spec is very specific about input/output shapes (only `fb`/`ob`/`snp`/`gtag`, channels `ono1`..`ono99999`, fields like `allocated_at`). Pydantic enforces those types at the API boundary so the rest of the code can trust the data and I can't accidentally drift from the spec.
- **React + Vite** for the frontend. Vite has near-instant dev reloads and a tiny config, and React is what I'm fastest in for "form + table + a few buttons". No bundler pain, no boilerplate.
- **In-memory store** behind a repository class. Persistence wasn't required by the spec, and the abstraction means I can swap to SQLite later without touching the service or routes.
- **Cancel by `channel`** (not `ad_id + platform`). One key, matches the Free input, simpler frontend.
- **Duplicate active `(ad_id, platform)` -> 409 conflict** with the existing allocation in `details`. Picked this over silent idempotent because clients should know they hit a duplicate.
- **Free on non-active channel -> 409**, same reasoning. Explicit errors > silent passes.

## What I corrected as I went

- I went through every error response the API returns and compared it to the spec wording. Renamed some `error_code`s, tightened messages, made sure the boundary cases (cancel at exactly 5:00 minutes, freed_at exactly at NY midnight) matched what the spec says.
- The AI initially used a fixed 24h cooldown — I switched it to the bonus advanced cooldown (next NY midnight after `freed_at + 24h`) and updated the timing assertions in the tests to match.
- Fixed Windows-specific issues the AI missed at first: `tzdata` was needed for `zoneinfo` to find `America/New_York`, and `uvicorn` only works after activating the venv (or running it through the venv's Python).
- Pushed back when the AI suggested SQLite + SQLAlchemy. For a 3-4h scope, in-memory was the right call.

## What stayed mine

- Scope and tradeoffs: in-memory vs DB, which bonus items to do, what the error envelope should look like.
- API shape: endpoint paths, status codes, the choices the spec asked me to "choose and document".
- Tech stack: FastAPI + Pydantic backend, React + Vite frontend.
- Final review: I read every diff before accepting it, ran the tests myself, and called out anything that didn't match the spec.
