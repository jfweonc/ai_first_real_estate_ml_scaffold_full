# AI‑First Real Estate ML — **Codex Working Context**  
_Last updated: 2025‑09‑29 (America/Chicago)_

> **Purpose:** This single file gives Codex (or any code LLM in VS Code) the exact project context, conventions, contracts, roles, and next actions so it can generate correct code, tests, and docs without extra back‑and‑forth.

---

## 1) Project Snapshot (TL;DR)

- **Goal:** Build an AI‑first, reproducible pipeline to ingest Houston/Sugar Land HAR MLS data (sales & rentals, 1996‑present), normalize/dedupe, index images, geocode, and (later) train multimodal models (tabular + images) to predict price/ROI.
- **Owner & environment:** Solo developer on Windows + Docker; runs code in containers when possible; prefers **idempotent ETL** and **deterministic builds**.
- **Key preferences:**
  - Keep modules ≤ ~200 LOC, pure functions, typed; docstrings + small CLIs.
  - Pinned deps, pre‑commit, ruff/black, pytest. Reproducible via Docker Compose.
  - **MapTiler** for geocoding (cost‑effective; incremental updates only).
  - **Images:** SHA‑based indexing; per‑listing checks: `images_download_status ∈ {none, partial, complete}`, `images_count`, `images_last_checked`.
  - **Semi‑automatic slicing (policy‑driven) for agents**: Manager plans → specialists implement → tests/CI gate → rework loop until green.
- **Data roots (relative to repo):**
  - `data/raw/` (CSV, zips, as‑received)  
  - `data/interim/` (normalized images, clean CSV slices)  
  - `data/processed/` (Parquet/DB exports, features)  
  - `data/reports/` (coverage, quarantine, conflicts, data quality)  
  - Images normalize to `data/raw/{SALE|RENTAL}/images/{listing_key}/<original>.jpg`

---

## 2) Repo Layout & What Each File Is For

```
.
|-- README.md
|-- .env.sample            # Example env vars; copy to .env for local/dev
|-- .gitignore / .gitattributes
|-- requirements.txt       # Pinned deps (Python 3.11+ recommended)
|-- pre-commit-config.yaml # Lint/format/static checks on commit (ruff, black, etc.)
|-- pyproject.toml         # Tool configs (ruff, black, pytest, mypy)
|-- .vscode/
|   `-- tasks.json          # One-click tasks (lint/test/build/data jobs)
|-- .github/workflows/
|   `-- ci.yml              # CI: install, lint, test; block merges on red
|-- .agents/
|   |-- manager.md          # AI prompt for Manager (architect/orchestrator)
|   |-- pm.md               # AI prompt for Product Manager
|   |-- architect.md        # AI prompt for Solution Architect
|   |-- backend.md          # AI prompt for Backend/ETL engineer
|   |-- test.md             # AI prompt for Test engineer
|   |-- data_ml.md          # AI prompt for Data/ML specialist
|   |-- security.md         # AI prompt for Security
|   `-- sre.md              # AI prompt for SRE
|-- context/
|   |-- file_map.md
|   |-- phase_plan.md
|   |-- project_goals.md
|   `-- tech_stack.md
|-- docs/
|   |-- backlog.md
|   |-- backlog.yaml
|   |-- decisions/
|   |-- roles/
|   `-- runbook_etl.md
|-- src/relml/
|   |-- __init__.py
|   |-- cli.py              # Typer CLI entrypoint
|   |-- util/
|   |   `-- fs.py
|   `-- etl/
|       |-- __init__.py
|       `-- import_csv.py   # Current Phase 1 slice
|-- tests/
|   |-- test_cli_doctor.py
|   `-- specs/
|       |-- test_phase01_csv_ingest_spec.py
|       `-- test_phase01_validation_spec.py
|-- tools/
|   |-- agent_runner.py
|   |-- apply_patch.py
|   |-- capability_review.py
|   `-- conductor.py
|-- policy/
|   `-- orchestrator.yaml
|-- bus/
|   |-- capabilities.jsonl
|   |-- critiques/
|   |-- decisions/
|   |-- proposals/
|   `-- rfc/
`-- data/                   # Created at runtime; reports land here
```

**Why `.env.sample`?** Safe template of env vars; copy to `.env` (not committed).  
**Why ruff in both pre‑commit + pyproject?** `pyproject.toml` holds ruff settings; `pre-commit` just *invokes* ruff on staged files—no duplication, different layers.  
**CI ≡ Continuous Integration:** automated lint/test on PRs; blocks merges on red.

---

## 3) Working Agreements for Codex (Do These By Default)

1. **Plan first**: Produce a small plan (tasks + files touched). Then implement in small PR‑sized changes.
2. **Structure**: Functions pure where possible. Modules ≤ ~200 LOC. Strong typing. Docstrings (NumPy/Google style).
3. **Config**: No secrets in code. Read from `os.environ` or a `config.yaml`. Provide `.env.sample` keys.
4. **Paths**: Use `pathlib`. Normalize separators. Assume repo root mounting under Docker (Windows friendly).
5. **Logging**: `logging` with module loggers and `INFO/DEBUG`. No noisy prints.
6. **Idempotence**: Every ETL step safe to re‑run (no duplicates, consistent outputs).
7. **Tests**: Write/adjust tests with each change. Include edge cases + property checks where sensible.
8. **Docs**: Update README/ARCHITECTURE/PHASES when behavior or interfaces change.
9. **Performance**: Prefer streaming/iterators for large CSVs. Avoid loading entire files when not needed.
10. **Security/PII**: MLS data handled locally; no external uploads unless explicit.

---

## 4) Phase Roadmap (Order & Rationale)

> Current sequence: **Phase 0 -> Phase 0.5 -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5 -> Phase 6 -> Phase 7 -> Phase 8 -> Phase 9** (per docs/PhasePlan).

- **Phase 0 -- Charter & Repo Scaffold**
  - Pin tooling, guardrails, CI; publish ProjectBrief and Guardrails docs.
  - Stand up the repo skeleton and baseline automation hooks.
- **Phase 0.5 -- Orchestrator & Local Loop**
  - Ship the Typer CLI + guarded diff applier so agents can loop locally.
  - Seed VS Code tasks and .ai context for planning/apply/test/status.
- **Phase 1 -- Data Ingestion & Staging**
  - Ingest MLS/HAR CSVs with validation, quarantine, ledger, and samples.
  - Stage image manifests with hashes/status; emit coverage and selected_listings artifacts.
- **Phase 2 -- Tooling & Experimentation (EDA sandbox)**
  - Build reproducible notebooks/scripts fed only from staging outputs.
  - Generate hygiene reports (missingness, leakage, distributions) and export markdown.
- **Phase 3 -- ETL v1 (Clean & Normalize)**
  - Normalize listings into analysis tables with canonical keys and dedupe.
  - Share common transforms that feed downstream feature work.
- **Phase 4 -- Feature Engineering v1 (Tabular)**
  - Produce supervised feature matrices with aggregation windows and metadata.
  - Keep feature generation reproducible and stored for modeling.
- **Phase 5 -- Baseline Models (Tabular)**
  - Train time-aware tree baselines with conformal intervals and Optuna sweeps.
  - Track experiments in MLflow and evaluate modality lift.
- **Phase 6 -- Multimodal Add-On (Images + Tabular)**
  - Embed images, fuse modalities, and benchmark vs tabular baselines.
  - Cache embeddings and parallelize IO for throughput.
- **Phase 7 -- Packaging & MLOps Ready**
  - Package modules, version artifacts, and write runbooks/SLOs.
  - Provide scripts to train/evaluate/promote with traceable outputs.
- **Phase 8 -- Serving & Reporting (internal)**
  - Automate batch predictions and static reports; optional lightweight API.
  - Keep outputs linkable to their source data.
- **Phase 9 -- Monitoring, Drift & Retraining**
  - Monitor MAE/coverage/drift, alert on thresholds, and schedule retrains.
  - Track cost/performance and verify the retrain path end-to-end.
---

## 5) Data Contracts & Idempotence Keys

### 5.1 Staging (DB/Parquet)
- **Unique idempotence key:** `(mls_number, domain, MatrixModifiedDT)` + `normalized_row_hash`
- **Ledger table:** `etl.file_ingest_ledger(file_hash, path, ingested_at, rows, source)`
- **Quarantine file:** `data/reports/quarantine_rows.csv` for structural errors.
- **Conflicts file:** `data/reports/conflicts.csv` for key collisions or schema mismatches.

### 5.2 Images
- **Normalize to:** `data/raw/{SALE|RENTAL}/images/{listing_key}/<original>.jpg`
- **Parse filenames:** `{listingNumber}_{imageNumber}.*` (be robust to case/extra tokens).
- **Per‑listing checks (DB or parquet):**
  - `listing_key` (string; canonicalized)
  - `images_download_status` ∈ `{none, partial, complete}`
  - `images_count` (int)
  - `images_last_checked` (datetime)
  - `source` ∈ `{manual, automation}`
- **De‑dup by content:** store `sha1/sha256` and original filename; avoid dupes.

### 5.3 Geocoding (MapTiler)
- **Inputs:** address fields, ZIP5 (normalize `PostalCode → ZIP5`).
- **Idempotence:** cache by `(address_string_hash)`; **only geocode new rows**.
- **Outputs:** lat/lon, accuracy, provider, timestamp (Parquet/DB table).

---

## 6) Module Specs (what to build/extend)

### Module 1 – `src/relml/etl/import_csv.py`
**Inputs:** `data/raw/**/*.csv|CSV`  
**Process:**
- Discover files (`glob *.csv|*.CSV`); compute `sha256`.
- Skip if `file_hash` in `etl.file_ingest_ledger`.
- Schema sniff → validate headers & types. Quarantine bad rows.
- Normalize minimal fields (e.g., `ZIP5`, dates, strip whitespace).
- Write clean rows to staging (DB or Parquet). Record ledger row.
**Outputs:** clean slice + `data/reports/quarantine_rows.csv`, `conflicts.csv`  
**CLI:** `python -m src.relml.cli import-csv --root data/raw --dry-run` (Phase 1 slice)  
**Tests:** empty/malformed files, duplicate rows, idempotent re‑run, large file streaming.

### Module 2 – `src/relml/etl/index_images.py` (planned)
**Inputs:** zip folders, loose images: `data/raw/{SALE|RENTAL}/images_zip|images/`  
**Process:**
- Unzip to normalized tree; keep original filenames; compute hashes.
- Compute per‑listing checks (`images_count`, `images_last_checked`, `images_download_status`).
- Detect and tag `{manual|automation}` source.
**Outputs:** normalized image tree + **per‑listing check table**  
**CLI:** `python -m src.relml.cli index-images` (planned)  
**Tests:** weird filenames, dupes by content, partial listings, idempotence.

### Module 3 – `src/relml/etl/geocode.py` (planned)
**Inputs:** clean staging slice (addresses).  
**Process:** MapTiler geocode w/ caching; incremental only.  
**Outputs:** geocode table (lat/lon, accuracy, ts).  
**Tests:** cache hit/miss, rate‑limit/backoff, bad addresses.

### Module 4 – `src/relml/etl/dedupe.py` (planned)
**Inputs:** staging + geocode; optional image hashes.  
**Process:** deterministic blocking + fuzzy match; output canonical ID map.  
**Outputs:** deduped table + mapping.  
**Tests:** collisions, precision/recall samples, reproducibility.

---

## 7) Tooling & Commands

### Python & Tests
- **Run tests:** `pytest -q` (pytest auto‑discovers `test_*.py` / `*_test.py`)
- **Run single test:** `pytest -q tests/test_index_images.py::test_basic`
- **Install pre‑commit hooks:** `pre-commit install` → then `pre-commit run -a`

### Docker Compose
- **Build image:** `docker compose build app`
- **Start (build if needed, detached):** `docker compose up -d --build`
- `build` only builds. `up -d --build` builds **and** starts containers in background.

### VS Code
- Add handy entries in `.vscode/tasks.json` for: **Lint**, **Test**, **ETL: import_csv**, **ETL: index_images**, **Geocode**.

---

## 8) Coding Conventions (enforced)

- **Imports:** stdlib → third‑party → local.  
- **Type hints** everywhere; `from __future__ import annotations` if helpful.  
- **I/O** via `pathlib.Path`. No hard‑coded OS paths; no secrets in repo.  
- **Config:** `CONFIG_…` env vars documented in `.env.sample`.  
- **Errors:** raise specific exceptions; unit tests assert on them.  
- **Logging:** `logger = logging.getLogger(__name__)` with clear messages.  
- **Docs:** update `ARCHITECTURE.md` and `PHASES.md` when interfaces change.

---

## 9) Semi‑Automatic Slicing (Policy‑Driven)

We prefer **policy‑driven slicing**: the Manager agent decides the slice (scope/constraints) from PHASES, opens a plan (files, steps, tests), the Backend agent implements, the Test agent writes/updates tests, CI runs. If CI fails, Manager narrows/clarifies and repeats. Use `contracts/*.schema.json` to validate agent outputs.

**Manager loop template:**
1. Read `docs/PHASES.md` goals.
2. Produce a slice plan: _files to touch, acceptance criteria, tests to add_.
3. Call Backend to implement; call the Test agent to extend tests; re‑run CI.
4. If red, tighten plan or reduce scope; iterate until green.

---

## 10) Why `.agents/<role>.md` **and** `docs/roles/<role>.md`?

- `.agents/*.md` = **machine‑optimized prompts** (short, directive, with JSON I/O).  
- `docs/roles/*.md` = **human docs** (rationale, examples, org context).  
Keeping both avoids token bloat in prompts while preserving rich guidance for humans.

---

## 11) RFC vs Patch

- **RFC/Proposal**: Use when design has uncertainty or cross‑cutting impact. Lives in `docs/RFCs/NNN-title.md` with context, options, decision, and migration notes.
- **Direct patch + guide**: For low‑risk, obvious improvements (e.g., adding a CLI flag, fixing parsing). Include a short CHANGELOG entry and update relevant docs.

---

## 12) Data & Image Details (gotchas)

- Windows + Docker: Watch path lengths & CRLF/LF; set `.gitattributes` appropriately.
- Mixed casing/extensions (`.CSV` vs `.csv`) should be supported.
- Filenames may have spaces/unicode. Always **hash content** to de‑dup.
- `listing_key` canonicalization must be stable across modules.
- Maintain **source provenance** (`manual` vs `automation`).

---

## 13) Acceptance Criteria (per module change)

- Code conforms to style/lint; **pre‑commit clean**.
- Unit tests added/updated; meaningful coverage; all **CI green**.
- Idempotent re‑runs yield identical outputs.
- Docs updated (README/ARCHITECTURE/PHASES).
- CLI examples work (dry‑run mode is a plus).

---

## 14) Env Vars (`.env.sample` to copy)

```
# Database (optional; if not set, write Parquet in data/interim or processed)
DATABASE_URL=postgresql://app:app@db:5432/real_estate_ml_dev

# Geocoding
MAPTILER_API_KEY=__REPLACE_ME__

# General
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
```

---

## 15) FAQs Codex Should Know

**Q: How does pytest know which tests to run?**  
A: Discovery rules: `tests/` folder; files `test_*.py` or `*_test.py`; functions `test_*`.

**Q: Why not a single “overall config” instead of pre‑commit + pyproject?**  
A: Different scopes: pre‑commit orchestrates hooks; pyproject stores tool configs (ruff/black/mypy/pytest).

**Q: When to use `docker compose build` vs `up -d --build`?**  
A: `build` compiles images; `up -d --build` builds **and** starts services in background.

---

## 16) Glossary & Abbreviations

- **AI‑first**: Design the repo so AI agents can safely generate code.
- **CI**: Continuous Integration. Auto lint/test on PRs.
- **QA**: Quality Assurance (tests & verification).
- **SLA**: Service Level Agreement (performance/reliability promise).
- **SLO**: Service Level Objective (measurable target under the SLA).
- **RACI**: Responsible, Accountable, Consulted, Informed (roles grid).
- **Idempotent**: Safe to run multiple times, same result.
- **RFC**: Request for Comments (design proposal & decision record).

---

## 17) Immediate Next Slices for Codex (Do Now)

1. **Add per‑listing image check table** with CLI in `src/relml/etl/index_images.py`:
   - Compute and persist `images_count`, `images_last_checked`, `images_download_status`, `source`.
   - Idempotent: recompute without duplicating rows.
   - Tests for partial listings + duplicate content.
2. **Harden CSV ingest ledger** in `src/relml/etl/import_csv.py`:
   - Ledger write/read; skip by `sha256(file)`; quarantine malformed rows.
   - Emit `data/reports/quarantine_rows.csv` & `conflicts.csv`.
   - Tests: malformed headers, duplicate rows, large file streaming.
3. **Write `.env.sample`** with keys above; wire `DATABASE_URL` usage behind a feature flag (Parquet fallback).
4. **Add VS Code tasks** for lint/test/etl ops; update README usage examples.

> _Acceptance: CI green; tests pass locally; docs updated; CLIs runnable from repo root._

---

## 18) Minimal System Prompt Snippet for Codex

> You are **Backend** for AI‑First Real Estate ML. Follow the Working Agreements in this file. Before coding, output a short plan (files, changes, tests). Keep modules small, typed, and idempotent. Update tests/docs. If assumptions are needed, choose safe defaults and document them. Always make CI green.

---

## 19) Project Context & Preferences (for better suggestions)

- User is a licensed **real estate agent** with MLS access, focused on Houston/Sugar Land.  
- Prefers **MapTiler** geocoding, Windows‑friendly tooling, Docker reproducibility.  
- Wants ingestion and coverage solid in Phase 1 before pushing later automation slices.  
- Emphasizes **automation, tests, and docs**; expects small, composable modules.

---

## 20) Appendices

### A) DB utilities (`src/relml/etl/utils/db.py` planned)
- `connect()` from `DATABASE_URL` env; contextmanager for cursors.
- `file_already_ingested(cur, file_hash: str) -> bool` — check `etl.file_ingest_ledger`.
- Migrations: simple `CREATE TABLE IF NOT EXISTS` helpers.

### B) Media utilities (`src/relml/etl/utils/media_util.py` planned)
- `sha256_file(path: Path) -> str` — stream read in chunks (8192 bytes).
- Safe unzip, extension normalization, and content hashing.

### C) Recon scripts
- `scripts/recon/report_coverage.py` → emit per‑zip/listing coverage HTML in `data/reports/`.

### D) Windows Tips
- Use `pathlib` and avoid absolute drive letters.
- Normalize newlines with `.gitattributes` to prevent churn.

---

**That’s it.** Use this file as the single source of truth while you generate code, tests, and docs.
