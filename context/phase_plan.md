# Phase Overview

Phase 0 (done): Charter and repo scaffold.
- Align on goals, tooling, CI, and guardrails.

Phase 0.5 -- Orchestrator & Local Loop
- Stand up the emit -> request -> plan -> patch -> apply -> test -> status loop.
- Provide guarded diff apply, Typer CLI commands, and VS Code tasks.

Phase 1 -- Data Ingestion & Staging
- Ingest MLS/HAR CSVs with schema validation, quarantine, and ledger tracking.
- Stage images with hashes and status metrics; emit clean samples for fast tests.
- Publish coverage summaries plus selected_listings manifests for downstream work.

Phase 2 -- Tooling & Experimentation (EDA sandbox)
- Build reproducible notebooks/scripts that read staging tables only.
- Generate hygiene reports (missingness, leakage checks, distributions) and persist markdown exports.

Phase 3 -- ETL v1 (Clean & Normalize)
- Normalize listings into analysis-ready tables with consistent keys and types.
- Handle dedupe, address cleaning, and shared transformations for features.

Phase 4 -- Feature Engineering v1 (Tabular)
- Derive supervised features, aggregation windows, and target encodings.
- Persist feature matrices with metadata for reuse by modeling.

Phase 5 -- Baseline Models (Tabular)
- Train time-aware tree baselines with coverage-aware metrics and conformal intervals.
- Track experiments (Optuna, MLflow) and evaluate modality lift.

Phase 5.5 -- Analysis
- Explain models with SHAP/ALE/PDP, run ablations, and document takeaways.

Phase 5.6 -- Evaluation & Promotion
- Run champion/challenger flows with promotion rules and registry updates.

Phase 5.7 -- Monitoring & Alerts
- Ship dashboards and alerting for MAE, coverage, drift (PSI/KS).

Phase 5.8 -- Auto-Optimization Loop
- Trigger retunes on drift, schedule, or new data and re-run promotion gates.

Phase 5.9 -- Ops Playbooks
- Maintain runbooks for promote/pause/demote plus retention/backups.

Phase 6 -- Multimodal Add-On (Images + Tabular)
- Embed images, fuse modalities, and benchmark against tabular baselines.

Phase 7 -- Packaging & MLOps Ready
- Package modules, version artifacts, and provide runbooks/SLOs.

Phase 8 -- Serving & Reporting (internal)
- Automate batch predictions, static reports, and optional lightweight API.

Phase 9 -- Monitoring, Drift & Retraining
- Close the loop with drift detection, scheduled retraining, and cost tracking.
