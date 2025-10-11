# Phase Plan

## Phase 0 - Charter & Repo Scaffold

**Objective:** Align on goals, constraints, and create a clean, reproducible repo.

**Key tasks**

- Write **ProjectBrief.md** (goals, metrics, data sources, model scope, risks).
- Create repo skeleton: `src/`, `etl/`, `tests/`, `docs/`, `phases/`, `.ai/`, `samples/`.
- Pin tooling: `pyproject.toml`/`requirements.txt`, `pre-commit`, `ruff`, `mypy`, `pytest`.
- Add CI basics (`.github/workflows/ci.yml`) running lint + unit tests.
- Draft **Guardrails** (=200 LOC/module, naming, logging, error handling).

**Artifacts**

- `docs/ProjectBrief.md`, `docs/Guardrails.md`, repo tree, initial CI.

### Modules (Phase 0 Charter Slice)
- **P0-M1 Charter & Brief:** `docs/ProjectBrief.md`, guardrails, and scope alignment.
- **P0-M2 Repo Scaffold:** baseline directory tree, tooling pins (`pyproject.toml`, `requirements.txt`, `.pre-commit-config.yaml`).
- **P0-M3 CI & Quality Gates:** GitHub Actions / linting, `pre-commit`, `ruff`, `mypy`, core pytest smoke.
- **P0-M4 Developer Environment:** `.vscode/` tasks, `.env.sample`, bootstrap scripts (`make init`, virtualenv docs).

**Acceptance**

- CI green; `pre-commit run --all-files` clean.

**Automation hooks**

- `make init` or `uv pip install -r requirements.txt`
- CI job: lint + tests on PR.

**Notes**

- Keep this lean; detail expands later.

---

## Phase 0.5 - Orchestrator & Local Loop

**Objective:** Install the loop: Emit ? Request (plan) ? Plan (3a) ? Patch (3b) ? Apply ? Test ? Status/Handoff.

**Key tasks**

- Add CLI (`orchestrator/cli.py`) with commands: `emit`, `make-request`, `call-gpt5` (optional), `apply`, `test`, `status`.
- Add safe diff applier (`orchestrator/diff_utils.py`) with allowlist & path-traversal checks.
- Add VS Code tasks for one-click running.
- Create phase manifest template `phases/phase_current_manifest.yaml`.
- Seed `.ai/context.toml` (version pins).

**Artifacts**

- `.vscode/tasks.json`, `.ai/status.md`, `.ai/bus/request_for_gpt5.txt`, tests for applier.

### Modules (Phase 0.5 Orchestrator Slice)
- **P0.5-M1 CLI Scaffolding:** `orchestrator/cli.py` commands (`emit`, `plan-request`, `make-request`, `apply`, `test`, `status`), Typer wiring.
- **P0.5-M2 Patch Guard:** `orchestrator/diff_utils.py` allowlist enforcement, AST validation, tests (`tests/test_orchestrator_min.py`).
- **P0.5-M3 VS Code & Automation:** `.vscode/tasks.json`, `.ai/context.toml`, loop tasks (`apply`, `test`, `status`, planning request).
- **P0.5-M4 Runbook & Status:** `.ai/status.md`, doc updates (`docs/OrchestratorWorkflow.md`, `docs/reports/phase05_manual_log.md`) capturing the local loop.

**Acceptance**

- `python -m orchestrator.cli apply patches/0001.diff` works and blocks disallowed paths.
- `pytest -q ::tests/test_orchestrator_min.py` passes.

**Automation hooks**

- Tasks: AI: Apply Patch, AI: Test (quick), AI: Status, AI: Build planning request, AI: (opt) Call GPT-5.

**Notes**

- Split Step 3 into 3a (Plan) and 3b (Patch).

---

## Phase 1 - Data Ingestion & Staging

**Objective:** Bring raw MLS/HAR data (+ images) into a controlled staging area.

**Key tasks**

- Define data contracts (file layouts, required columns, types) for sales and rental feeds.
- Implement stage loaders with row/file hashing, presence-only counts, and duplicate reporting.
- Image ingestion: unpack HAR zip bundles, compute SHA-1 per asset, and persist manifests plus per-listing folders.
- Create 20-50 row gold samples for fast unit tests.
- Add tests for malformed rows, missing fields, missing-image flows, and unexpected encodings.

**Artifacts**

- `etl/stage_listings.py`, `etl/stage_images.py`, `schemas/mls_schema.sql`, `samples/`, `tests/test_stage_*.py`.

### Modules (Phase 1 Data Ingestion Slice)
- **P1-M1 Validation Core:** enforce required columns, row validation, counts, structured logging.
- **P1-M2 Ledger Persistence & Idempotence:** write `etl_ledger` rows, skip duplicates, tolerate missing `DATABASE_URL`.
- **P1-M3 Quarantine Artifact:** dedupe and persist `reports/quarantine_rows.csv` with `_source_file` and `_reason`.
- **P1-M4 Clean Export & Coverage:** emit `clean_listings.csv`, `coverage_summary.md`, and `selected_listings.csv` with gap reasons.
- **P1-M5 CLI UX & Events:** CLI prints coverage summary/artifact paths and logs `cli.import_csv.complete` with payload.
- **P1-M6 Images Manifest Summary:** optional `--images-manifest` argument attaches per-listing counts/status buckets.
- **P1-M7 Docs & Handoff:** refresh runbooks, manual logs, and manifests to describe artifacts and orchestrator loop.

### Modules (Phase 1 Staging Loaders)
- **P1-S1 Stage Listings Loader:** `etl/stage_listings.py` dedupes by `(listing_key, domain)` and keeps the newest `matrix_modified_dt`, emitting row/file hashes and `_source_*` metadata.
- **P1-S2 Stage Images Loader:** `etl/stage_images.py` summarizes listing-image manifests into `stage/images_summary.json` with `complete`, `partial`, `missing`, and `no_images` tags.
- **P1-S2b Image Zip Extractor:** unpack `Data/Raw/{SALE|RENTAL}/images/*.zip` into per-listing folders, write newline-delimited manifests keyed by `(listing_key, sha1)`, and skip duplicates on re-run.
- **P1-S3 Gold Sample Builder:** generate deterministic 20-50 row CSV/JSON samples plus helper stats for tests and analysts.
- **P1-S4 Robustness & Edge Cases:** exercise missing identity, invalid timestamps/JSON, duplicate hashes, and dry-run behaviour.
- **P1-S5 Staging Runbook & Monitoring:** update `docs/runbook_etl.md` with staging flows, dedupe reports, and quick health checks.

### Modules (Phase 1 Acquisition Ops)
- **P1-A1 Coverage Tracker:** `etl/acq_status.py` creates `acq_daily_status` (presence-only COMPLETE/MISSING) and records per-listing image statuses (`complete`, `no_images`, `partial`, `failed`).
- **P1-A2 Gap Detector:** `etl/gap_detector.py` buckets staged listings by `matrix_modified_dt::date`, reports missing days, and surfaces image gaps by ZIP/date; configurable source (`stage` or `raw`).
- **P1-A3 HAR Downloader:** `etl/har_downloader.py` plus `etl/har_browser.py` plan/download HAR data with Playwright, honour per-run caps (<=5000 listings, <=100 listing images), zip filters, `--today` partials, and dry-run planning.
- **P1-A4 Acquisition Runbook & Tasks:** `configs/acq.yaml`, VS Code tasks (Detect gaps, Download HAR, Mark today partial), and `docs/P1_Acq_Operations.md` describing daily ops and rate/backoff guidance.

**Acceptance**

- `etl/stage_*` load sample files deterministically; null/malformed handling covered by tests.

**Automation hooks**

- `reml emit` -> "Plan loaders for X formats".
- Local plugin produces patch; `reml apply` -> `reml test`.

**Notes**

- Keep staging idempotent and append-only; log ingestion stats.

## Phase 2 - Tooling & Experimentation (EDA sandbox)

**Objective:** Establish fast EDA workflows and feature sniffing without polluting ETL.

**Key tasks**

- Notebooks/scripts reading staged data only.
- Data hygiene reports: missingness, distributions, leakage checks.
- Correlations, target leakage scan, categorical cardinality, outlier policy.
- Persist EDA findings into `docs/eda/*.md` (export from notebooks).

**Artifacts**

- `notebooks/eda/*.ipynb` (or `src/eda/*.py`), `docs/eda/summary.md`.

**Acceptance**

- EDA report generated reproducibly from one command; checked into `docs/`.

**Automation hooks**

- `make eda` or `python -m eda.run --out docs/eda/summary.md`.

**Notes**

- Use small samples by default; full runs only in CI/nightly.

---

## Phase 3 - ETL v1 (Clean & Normalize)

**Objective:** Produce a normalized, analysis-ready layer.

**Key tasks**

- Address normalization, date parsing, unit conversion, categorical harmonization.
- Deduplicate across listing refreshes; stable keys.
- Persist to normalized tables; add v1 data dictionary.

**Artifacts**

- `etl/normalize_*.py`, `docs/data_dictionary_v1.md`, `tests/test_normalize_*.py`.

**Acceptance**

- Deterministic output on sample inputs; duplicates reduced per rule; column types validated.

**Automation hooks**

- Manifests per submodule (e.g., `phase_03_addresses.yaml` with targets/tests).

**Notes**

- Emit lineage columns (source file, load_ts, hash) for traceability.

---

## Phase 4 - Feature Engineering v1 (Tabular)

**Objective:** Build features and a curated dataset for classical models.

**Key tasks**

- Define feature spec (lags, rolling stats, text hashes, geofeatures).
- Implement `features/build.py` producing Parquet.
- Add leakage fences and train/val/test splits by time.

**Artifacts**

- `features/build.py`, `features/schema.yaml`, `tests/test_features.py`.

**Acceptance**

- Feature build reproducible; schema validated; split integrity enforced.

**Automation hooks**

- `python -m features.build --since 2015-01-01 --out data/features_v1.parquet`.

**Notes**

- Log feature importances later to prune.

---

## Phase 5 - Baseline Models (Tabular)

**Objective:** Establish strong baselines and evaluation harness.

**Key tasks**

- Train/test Linear, RandomForest, XGBoost/LightGBM with sensible defaults.
- Implement evaluation: MAE/MAPE/RMSE, calibration plots, error buckets by price band/ZIP.
- Save model cards, params, metrics.

**Artifacts**

- `models/baseline/*.py`, `reports/model_cards/*.md`, `tests/test_eval.py`.

**Acceptance**

- Reproducible metrics; baseline thresholds documented (e.g., MAPE = X%).

**Automation hooks**

- `python -m models.baseline.train --dataset data/features_v1.parquet --out artifacts/baseline/`.

**Notes**

- Lock seeds; log dataset hash.

---

## Phase 6 - Multimodal Add-On (Images + Tabular)

**Objective:** Add image embeddings to improve predictions.

**Key tasks**

- Precompute embeddings (CLIP/DINOv2) for staged images; store as vectors/PCA.
- Join embeddings with tabular features; retrain boosted trees or shallow NN.
- Measure lift vs baselines; ablations with/without images.

**Artifacts**

- `vision/embed.py`, `features/join_vision.py`, updated model scripts.

**Acceptance**

- Statistically significant improvement on validation; runtime under target.

**Automation hooks**

- `python -m vision.embed --images data/stage/images/ --out data/embeddings/`.

**Notes**

- Cache embeddings; parallelize IO.

---

## Phase 7 - Packaging & MLOps Ready

**Objective:** Make it easy to run, test, and reproduce.

**Key tasks**

- Package modules; data versioning tags; promote artifacts.
- Add model registry stub (local FS) with metadata JSON.
- Documentation: runbooks, operational SLOs.

**Artifacts**

- `ARCHITECTURE.md`, `docs/runbook.md`, `registry/`, `scripts/promote.py`.

**Acceptance**

- One command to train/evaluate/promote; artifacts traceable.

**Automation hooks**

- GitHub Actions to build features ? train ? eval ? publish report on main.

**Notes**

- Keep secrets out; inject via `.env` only.

---

## Phase 8 - Serving & Reporting (internal)

**Objective:** Generate consumable outputs for yourself/partners.

**Key tasks**

- Static reporting (Markdown/HTML): top errors, ZIP insights, trend charts.
- Batch prediction script on new listings; CSV/Parquet outputs.
- Optional lightweight API (FastAPI) behind auth.

**Artifacts**

- `reporting/build_reports.py`, `api/app.py` (optional), `docs/reports/index.html`.

**Acceptance**

- Nightly report published; batch predict job passes smoke tests.

**Automation hooks**

- `python -m reporting.build_reports --since 7d`.

**Notes**

- Keep it simple; start with static pages.

---

## Phase 9 - Monitoring, Drift & Retraining

**Objective:** Close the loop.

**Key tasks**

- Data drift monitors (KS/PSI), performance decay tracking, alert thresholds.
- Scheduled retraining pipelines; backfills; compare to last promoted model.
- Cost/perf dashboards (tokens, compute, storage).

**Artifacts**

- `monitoring/drift.py`, `monitoring/perf_tracker.py`, dashboards.

**Acceptance**

- Alerts trigger on real drift; retrain path verified.

**Automation hooks**

- `python -m monitoring.check --window 30d`.

**Notes**

- Keep alerts low-noise; actionable.

---

## Phase manifests pattern

For each sub-phase:

```yaml
phase: 03_addresses
targets:
  - etl/normalize_address.py
  - tests/test_address.py
halo:
  - etl/common/strings.py
acceptance:
  - "pytest -q ::tests/test_address.py::test_usps_normalization"
context_refs:
  brief: project_brief@v1
  schema: mls_schema@v3
  guardrails: guardrails@v2
constraints:
  py: "3.11"
  style: "ruff"
```

---

## Daily loop (cheat-sheet)

1. `reml emit` ? build status.
2. GPT-5 (plan-only) ? returns targets + acceptance.
3. VS Code plugin (Patch Mode) ? produce unified diff(s).
4. `reml apply patches/xxxx.diff` ? guarded write.
5. `reml test` ? focused tests.
6. `reml status` ? write `.ai/status.md`; `reml make-request` ? paste-ready prompt.


