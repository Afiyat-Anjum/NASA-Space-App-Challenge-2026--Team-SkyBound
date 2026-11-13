# CLAUDE.md — Project Rules for Coding Agents

## Architectural Layer Discipline (Mandatory)
Read top to bottom and preserve strict separation of concerns:
1. **Frontend (`web/` and `app.py`) NEVER calls NASA directly.** It communicates exclusively with `src/api/` or static `demo_fixtures/`.
2. **API layer (`src/api/`) NEVER calls NASA during a demo.** It reads strictly from local `demo_fixtures/` (or pre-populated `cache/`).
3. **Acquisition layer (`src/acquire/`) 
4. **Compute layer (`src/compute/`) is pure deterministic science — NO LLM calls or probabilistic generative models inside `src/compute/`.**
5. **Agents (`src/agents/`) sit beside `src/api/` and reach data ONLY through typed tool schemas** defined in `src/agents/tools.py`.

## Scientific Invariants
- Spatial grid resolution: **5.5 km** (`~0.0494°`).
- Confidence filter: **>= 50** (mapping VIIRS `n` -> 75, `h` -> 95).
- Deduplication rule: Collapse multiple same-day detections inside a single 5.5 km cell to **1 active fire-cell event/day**.
- Baseline window: Circular **±7-day** historical Day-of-Year (DOY) empirical distribution.
