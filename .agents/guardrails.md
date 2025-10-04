# Guardrails (mandatory for all roles)

## Tooling & Quality
- Lint: ruff; Format: black; Imports: isort; Types: mypy --strict
- Tests: coverage_min ≥ 0.90 (behavioral > line)
- Logging: structlog JSON, ISO-8601 timestamps, request/job correlation IDs

## Data & Migrations
- Migrations: Alembic **SQL-only** (explicit DDL, forward + rollback)
- Idempotence keys:
  - CSV PK: (listing_key, domain, matrix_modified_dt)
  - Image UNIQUE: (listing_key, domain, sha1)

## Prompts & Outputs
- Prompts small (5–15 files, ≤400 KB). Output JSON or unified diff. No shell execution.
- Auto-extend policy:
  - GREEN/YELLOW → proceed with thin safe slice + `capability_notice`
  - RED → STOP with `capability_request` + ADR stub

## Security & Compliance
- Secrets via env/CI; no secrets in code or logs.
- PII classification before ingest; follow scraping policy.

## Observability
- Emit counters for ingest rows, dedup drops, backfill progress.
- SLO probes for critical paths; dashboards link from reports.

**Out-of-Scope Protocol (embed in each role)**
- If beyond remit:
  - GREEN/YELLOW → emit `capability_notice` and continue safely.
  - RED → emit `capability_request` and STOP.
