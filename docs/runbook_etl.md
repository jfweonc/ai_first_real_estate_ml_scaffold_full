# ETL Runbook

## Import CSV (Phase 1 slice)
- Discover only (no writes): `python -m orchestrator.cli import-csv --root data/raw --dry-run`
- Full ingest: `python -m orchestrator.cli import-csv --root data/raw [--images-manifest fixtures/p1/images_manifest_sample.jsonl]`
- CLI output prints coverage summary plus any artifact paths (quarantine, clean export, coverage report, gap manifest).
- Structured log event `cli.import_csv.complete` includes the full result payload:
  - `summary.coverage_metrics` with totals, per-domain stats, and gap counts.
  - `summary.ledgers` describing ledger writes (status `ledger_disabled` if `DATABASE_URL` is absent).
  - `summary.images_summary` when `--images-manifest` is supplied.

### Artifacts (written when not dry-run)
- `RELML_DATA_ROOT/reports/quarantine_rows.csv`
- `RELML_DATA_ROOT/reports/clean_listings.csv`
- `RELML_DATA_ROOT/reports/coverage_summary.md`
- `RELML_DATA_ROOT/reports/selected_listings.csv`

### Ledger behavior
- Requires `DATABASE_URL=postgresql://...`; otherwise the pipeline runs and records `ledger_disabled`.
- Idempotent per `file_hash`; reruns skip files already journaled in `etl_ledger`.

## Index Images
- Normalize into data/raw/{SALE|RENTAL}/images/{listing_key}/{n}.jpg, compute counts/status.
- Optional manifest summary via --images-manifest path/to/images_manifest.jsonl.

## Geocode
- MapTiler with caching; add lat/lon.

## Idempotence Targets
- CSV by file_hash; images by content hash; geocode cached by normalized address.
- Quarantine rows deduplicated by source + listing identity + reasons.

## Operational Tips
- Always run python -m orchestrator.cli status after apply/test to update .ai/status.md.
- Ledger writes require DATABASE_URL; without it the pipeline still emits coverage artifacts (ledger skipped).

## Stage Listings
- Source: stage_listings(root, dry_run=False)
- Input: CSVs under ingest root (see Phase 1 CLI output).
- Output: RELML_DATA_ROOT/stage/listings.csv with latest rows per (listing_key, domain) plus _source_file, _source_hash, _staged_at.
- Idempotence: uses SHA-256 of source file; reruns overwrite staging file deterministically.

## Stage Images
- Source: JSONL manifests (one per directory).
- Input: images.jsonl with listing metadata, filename, sha1.
- Output: RELML_DATA_ROOT/stage/images_summary.json summarizing per-listing counts and status (
one, partial, complete).
- Errors: invalid JSON lines skipped with warning; missing identity rows ignored.

## Build Stage Samples
- Command: uild_stage_samples(sample_size=20) (see src/relml/etl/stage_samples.py).
- Outputs: RELML_DATA_ROOT/samples/stage_listings_sample.csv and stage_images_sample.json.
- Dry run: dry_run=True inspects stage outputs without writing samples.
- Usage: Feed quick unit tests and manual inspection; sample size defaults to 20, capped by available staged rows.

