# Runbook: ETL
- Rerun job: relml import-csv --root data/raw
- Reindex images: relml index-images --root data/raw --source automation
- Quarantine/conflicts reports live in data/reports/
- Rollback migration: alembic downgrade -1 (SQL-only migrations)
