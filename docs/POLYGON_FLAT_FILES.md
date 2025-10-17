# Polygon Flat Files (S3) Support

The Data service now supports Polygon.io Flat Files via an S3-compatible endpoint.
You can list, sample, and download large historical datasets directly, avoiding many REST calls.

## Credentials

Provide your Polygon Flat Files S3 credentials using either environment variables or by storing them via the Providers Settings UI/API.

- Environment variables (recommended for infra):
  - `POLYGON_S3_ACCESS_KEY`
  - `POLYGON_S3_SECRET_KEY`

- Providers Settings (stored server-side, optional encryption-at-rest):
  - Provider ID: `polygon_flatfiles`
  - POST `/data/providers/polygon_flatfiles/key` with JSON `{ "api_key": "<access_key>", "secret": "<secret_key>" }`

Notes:

- Endpoint URL is hardcoded to `https://files.polygon.io` and bucket `flatfiles`.
- Credentials are used only for S3 Flat Files and are separate from the regular `POLYGON_API_KEY` (REST).

## Endpoints

Base path under the Data service (`/data`).

- List objects:
  - `GET /providers/polygon/flatfiles/list?prefix=<prefix>&max=500`
  - Example prefix: `us_stocks_sip/minute_v1/2024/03/`
  - Response: `{ ok, count, items: [{ key, size, last_modified, storage_class }] }`

- Sample a gzip CSV file:
  - `GET /providers/polygon/flatfiles/sample?key=<s3_key>&n=5&header=true`
  - Returns first N lines (optionally skipping header) from the object.

- Download an object to managed storage:
  - `POST /providers/polygon/flatfiles/download`
  - Body: `{ "key": "<s3_key>", "dest": "(optional absolute path under managed dir)" }`
  - If `dest` is omitted, saves to: `${FKS_DATA_DIR or ./data/managed}/polygon_flatfiles/<key>`

## UI Integration

In the React app under Settings → Market Data Providers, a quick test is available for "Polygon Flat Files (S3)". It lists a few objects under a common prefix and samples the first file.

## Requirements

- `boto3` is already included in `src/python/requirements.txt`.
- Ensure outbound internet access from the Data service container to `files.polygon.io`.

## Troubleshooting

- If you see `boto3 not available`, ensure dependencies are installed for the service image.
- If you see `Missing Polygon Flat Files S3 credentials`, set the env vars or save keys via the provider key API/Settings.
- Some prefixes are subscription-tier gated; listing may return 0 items if not entitled.
