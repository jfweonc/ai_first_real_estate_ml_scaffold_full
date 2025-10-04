Drop these into your repo:
- contracts/*.schema.json
- db/ddl/etl_ledger.sql
- tests/fixtures/import_csv/*.csv
- tests/fixtures/images/sample_bundle.zip
- docs/orchestration_contract.md
- docs/runbook_etl.md
- context/backlog_priorities.md
- context/coverage_expectations.md
- patches/vscode_tasks.diff

Then:
1) Apply db/ddl/etl_ledger.sql to your DB.
2) Try: python -m relml import-csv --root tests/fixtures/import_csv --dry-run
3) Implement ledger/validation/write; extend tests accordingly.