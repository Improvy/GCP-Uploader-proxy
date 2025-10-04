# Proxy for uploading files to GCP Storage

This project provides a proxy API for uploading files to Google Cloud Storage. The
proxy validates uploads, enforces optional file type and size limits, and publishes the
uploaded object so it can be consumed by client applications.

## Configuration

The container expects a service account with permission to upload objects to the
target bucket (for example the `Storage Object Creator` role). Download the JSON key
for that account and mount it inside the container. The following environment
variables are recognised:

| Variable | Required | Description |
| --- | --- | --- |
| `GCP_BUCKET` | ✅ | Name of the destination Google Cloud Storage bucket. |
| `GCP_CREDENTIALS_PATH` | ✅ | Absolute path to the mounted service account JSON file. |
| `ALLOWED_FILES` | ❌ | Comma separated list of allowed file extensions (e.g. `.jpg,.png`). |
| `UPROXY_MAX_FILESIZE` | ❌ | Maximum allowed file size in **megabytes**. Requests above the limit are rejected with HTTP `413`. |
| `UPROXY_PORT` | ❌ | Listening port inside the container. Defaults to `8000`. |

All responses follow the structure:

```json
{
  "code": <http_status_code>,
  "name": "<status_phrase>",
  "description": "<human_readable_description>"
}
```

## Running the proxy

### Docker

```bash
docker build -t gcp-uploader-proxy .

docker run -d \
  -p 8000:8000 \
  -e GCP_BUCKET="<your-gcp-bucket>" \
  -e GCP_CREDENTIALS_PATH=/mnt/secret/credentials.json \
  -e UPROXY_MAX_FILESIZE=10 \
  -v /path/to/credentials:/mnt/secret:ro \
  gcp-uploader-proxy:latest
```

Replace the placeholders with the correct bucket name and credentials path. If a
file larger than the configured size is uploaded the service returns HTTP 413
(`Request Entity Too Large`).

### Docker Compose (development)

```bash
docker compose up --build
```

The compose file expects a `.env` file with the configuration values listed above.
You can copy `.env.example` as a starting point. The `web/` directory is mounted
read-only for convenient local development.

## Example usage
```
curl --location --request POST 'http://<host>:<port>/upload' \
--form 'file=@"/path/to/upload.file"'

{
    "code": 200,
    "description": "https://storage.googleapis.com/<bucket_name>/<generated_filename>.file",
    "name": "Success"
}
```
