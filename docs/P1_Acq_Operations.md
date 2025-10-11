# Phase 1 Acquisition Operations

## Environment
- `DATABASE_URL`
- `HAR_USER`, `HAR_PASS` (HAR credentials)
- `RELML_DATA_ROOT` (e.g., `Data`)

## Daily Loop
1. Detect gaps (last 14 days).
2. Download missing/partial dates (honour `max_listings_per_run`, `max_images_listings_batch`).
3. Re-run gap detector.
4. Mark today partial (evening).

### Commands
- `python -m etl.gap_detector --since 14d --until yesterday`
- `python -m etl.har_downloader --since 14d --until yesterday --images --dry-run`
- `python -m etl.har_downloader --today`

## Rate Limits & Retries
- Listings ≤ 5000 per run.
- Images ≤ 100 listings per batch (partition by ZIP).
- Rate target ~2 req/sec, exponential backoff (1s → 30s with jitter).
- Status updates use `acq_daily_status` (`COMPLETE`, `MISSING`, `PARTIAL`) and `acq_image_status` (`complete`, `no_images`, `partial`, `failed`).

## Download Planner
- Presence-only status from staging (`Data/stage/listings.csv` or DB equivalent).
- Missing images computed via staged manifests; zip filters optional.
- `--today` marks current date partial without fetching.

## Image Extraction
- Zip bundles under `Data/Raw/{SALE|RENTAL}/images/*.zip` unpacked to `Data/stage/images/{domain}/{listing}`.
- Manifest (`manifest.jsonl`) contains `listing_key`, `domain`, `filename`, `sha1`, `source_zip`, `extracted_path`.
