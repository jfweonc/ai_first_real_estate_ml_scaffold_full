# Guardrails (mandatory for all roles)

- lint: ruff
- typecheck: mypy --strict
- tests: coverage_min: 0.90
- logging: structlog JSON, ISO-8601 timestamps
- migrations: Alembic SQL-only (explicit DDL)
- idempotence: CSV PK (listing_key, domain, matrix_modified_dt); image UNIQUE (listing_key, domain, sha1)
- prompts: small (5–15 files, <= 400 KB). Return JSON or unified diff. No shell execution.
- auto-extend policy: GREEN/YELLOW continue with notice; RED requires capability_request + ADR

**Out-of-Scope Protocol** (embed in each role):
- If beyond remit:
  - GREEN/YELLOW → emit `capability_notice` JSON and continue with a thin, safe slice + tests.
  - RED → emit `capability_request` JSON and STOP.
