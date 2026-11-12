# AI Use Disclosure & Attribution

## 1. AI Tools Used
- **Google Gemini (LLM Assistant):** Used for software scaffolding, FastAPI/Streamlit boilerplate structuring, Plotly color-scale configuration, and documentation formatting.

## 2. Example Prompts Used
- *"Design a deterministic Python pipeline to bin NASA FIRMS MODIS (1 km) and VIIRS (375 m) detections onto a 5.5 km grid and evaluate cross-sensor Pearson correlation."*
- *"Structure a 4-layer repository separating offline acquisition, deterministic compute, local-cache FastAPI endpoints, agent tools, and a static frontend."*

## 3. Human & Team Scientific Work
- **Problem Formulation & Domain Scope:** Selected South Asia (8 countries: Afghanistan, Bangladesh, Bhutan, India, Maldives, Nepal, Pakistan, Sri Lanka) across 2000–2026 to address agricultural residue burning and spring forest fire seasons across the November 2026 Suomi-NPP retirement window.
- **Data Acquisition & Curation:** Configured and downloaded 11.6+ million NASA FIRMS MODIS Collection 6.1 and VIIRS (S-NPP, NOAA-20, NOAA-21) records.
- **Parameter Selection & Verification:** Defined the 5.5 km cell-collapse rule and `confidence >= 50` filter, executed the pipeline, and verified the Pearson correlation improvement (`r = 0.8244` raw -> `r = 0.8503` harmonised over 5,355 overlap days).
