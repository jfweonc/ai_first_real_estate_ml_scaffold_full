# Phases (updated)

Phase 0 (done): env scaffold, Docker, repo skeleton.

Phase 0.5 — Manual ingest & coverage inventory
- Import manual CSVs/images.
- Compute media status fields in DB: images_download_status ∈ {none, partial, complete}, images_count, images_last_checked.
- Produce coverage reports (date & image) and a gap-fill manifest selected_listings.parquet.

Phase 2 — Automation (gap fill only)
- Playwright headful: export CSVs for uncovered dates; download all images for selected listings from the manifest.
- Idempotent (folder checks + DB uniqueness on (listing_key, domain, sha1)).

Phase 1 — Database & ETL (single clean pass)
- UPSERT listing; SCD2 listing_history on attribute changes.
- Geocode only missing/stale addresses (cache); PostGIS types & indexes.
- Image manifest & curation (sha1, pHash, dims).

Phase 3 — Features
- Emit {listing_key, domain, vector} for tabular/text/image; fuse.py joins/concats.
- Phase 3A (optional, early): zero-shot room tagging with CLIP prompts to pick one-per-room.

Phase 4 — Datasets (snapshot control)
- Build *_listprice.parquet and *_closeprice.parquet.

Phase 5 — Models & Intervals
- MVP: GBDT (LightGBM/CatBoost) per target (time-aware CV).
- Late fusion baseline (tab, text, image → meta-learner).
- Conformal prediction intervals (calibrated coverage).
- Optuna for tuning; MLflow for tracking.

Phase 5.5 — Analysis
- SHAP, permutation importance, ALE (default) / PDP (when weakly correlated), ablations (modality lift).

Added
Phase 5.6 — Evaluation & Promotion
- Champion/Challenger; MLflow Model Registry; auto-promotion rules.

Phase 5.7 — Monitoring & Alerts
- Daily metrics (MAE, coverage, PSI); alerts; dashboards.

Phase 5.8 — Auto-Optimization Loop
- Triggers: drift/perf breach, calendar, new data. Retune with Optuna and re-run promotion gate.

Phase 5.9 — Ops Playbooks
- Runbooks for pause/promote/demote; backups/retention.
