# Orchestration Contract (Agents, Models, Execution)
Date: 2025-09-30

Roles & Models
- Manager/Conductor -> gpt-5-thinking
- Specialist (Backend/Test) -> codex-latest
- Reviewer (Lint/Style) -> codex-latest

Execution Default
- Docker-first (compose services), fall back to host for quick lint/unit loops when needed.

Contracts
- CLI outputs -> contracts/processed_objects.schema.json
- Ledger writes -> contracts/etl_ledger.schema.json + db/ddl/etl_ledger.sql

Handoffs
- Manager pulls next story from context/backlog_priorities.md
- Specialist ships patch + tests + docs
- Reviewer enforces pre-commit/CI
