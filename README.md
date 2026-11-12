# FIRMS South Asia Active Fire Continuity & Burn Calendar

Harmonises 26+ years (2000–2026) of NASA FIRMS **MODIS Collection 6.1** (`MCD14ML`/`MCD14DL`) and **VIIRS 375m** (`VNP14IMGT` S-NPP, `VJ114IMGT` NOAA-20, `VJ214IMGT` NOAA-21) active fire detections across South Asia onto a common **5.5 km** spatial grid.

## Project Skeleton
```text
project/
├─ LICENSE                 # Apache-2.0
├─ README.md               # Overview, how to run, datasets
├─ CLAUDE.md               # Coding agent layer discipline rules
├─ AGENTS.md               # Portable agent instructions
├─ .claude/skills/         # Domain SKILL.md workflows
├─ .env.example            # Offline acquisition credentials template
├─ cache/                  # Gitignored raw NASA downloads
├─ demo_fixtures/          # Committed pre-harmonised Parquet & JSON bytes
├─ docs/AI_USE.md          # AI tool & prompt attribution
├─ src/
│  ├─ acquire/             # Offline NASA FIRMS downloader
│  ├─ compute/             # Deterministic 5.5 km harmonisation (no LLM)
│  ├─ agents/              # Tool schemas & orchestrator beside API
│  └─ api/                 # FastAPI local-cache service
└─ web/                    # Static frontend (HTML/JS/CSS)
```

## How to Run
1. **FastAPI + Static Web Frontend (`web/`):**
   ```bash
   pip install -r requirements.txt
   uvicorn src.api.main:app --host 0.0.0.0 --port 8000
   ```
   Open `http://localhost:8000` (API docs at `http://localhost:8000/docs`).
2. **Streamlit Interactive Dashboard (24/7 Cloud App):**
   ```bash
   streamlit run app.py
   ```

## Datasets & Validation
- **Source:** NASA FIRMS MODIS Collection 6.1 and VIIRS 375 m (S-NPP, NOAA-20, NOAA-21), 2000–2026 (11,617,834 detections with confidence >= 50 across 8 South Asian countries).
- **Cross-Sensor Validation (5,355 overlap days):** Pearson `r` improved from **0.8244** (raw) to **0.8503** (harmonised).
