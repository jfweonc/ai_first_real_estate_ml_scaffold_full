# ETL Runbook
1) Import CSV
- Dry run: python -m relml import-csv --root data/raw --dry-run
- Output follows contracts/processed_objects.schema.json
- Ingest: write ledger, quarantine bad rows, emit clean Parquet/DB

2) Index Images
- Normalize into .../images/{listing_key}/{n}.jpg, compute counts/status

3) Geocode
- MapTiler with caching; add lat/lon

Idempotence
- CSV by file_hash; images by content hash; geocode cached by normalized address