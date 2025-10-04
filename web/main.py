"""FastAPI application that proxies uploads to Google Cloud Storage."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Optional, Set, Tuple

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from google.api_core import exceptions as gcloud_exceptions
from google.cloud import storage
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

CHUNK_SIZE = 1024 * 1024  # 1MB


@dataclass(frozen=True)
class Settings:
    """Runtime configuration parsed from environment variables."""

    bucket: str
    credentials_path: Path
    allowed_extensions: Optional[Set[str]]
    max_file_size_bytes: Optional[int]

    @staticmethod
    def _parse_allowed_extensions(raw_value: Optional[str]) -> Optional[Set[str]]:
        if not raw_value:
            return None

        extensions: Set[str] = set()
        for item in raw_value.split(","):
            cleaned = item.strip().lower()
            if not cleaned:
                continue
            if not cleaned.startswith("."):
                cleaned = f".{cleaned}"
            extensions.add(cleaned)
        return extensions or None

    @classmethod
    def from_env(cls) -> "Settings":
        bucket = os.getenv("GCP_BUCKET")
        if not bucket:
            raise RuntimeError("GCP_BUCKET environment variable is required.")

        credentials_path_value = os.getenv("GCP_CREDENTIALS_PATH")
        if not credentials_path_value:
            raise RuntimeError("GCP_CREDENTIALS_PATH environment variable is required.")

        credentials_path = Path(credentials_path_value)
        if not credentials_path.is_file():
            raise RuntimeError(
                f"Credentials file '{credentials_path}' does not exist or is not a file."
            )

        allowed_extensions = cls._parse_allowed_extensions(os.getenv("ALLOWED_FILES"))

        max_file_size_raw = os.getenv("UPROXY_MAX_FILESIZE")
        max_file_size_bytes: Optional[int] = None
        if max_file_size_raw:
            try:
                max_file_size_bytes = int(max_file_size_raw) * 1024 * 1024
            except ValueError as exc:  # pragma: no cover - configuration error
                raise RuntimeError(
                    "UPROXY_MAX_FILESIZE must be an integer representing megabytes."
                ) from exc
            if max_file_size_bytes <= 0:
                raise RuntimeError("UPROXY_MAX_FILESIZE must be greater than zero.")

        return cls(
            bucket=bucket,
            credentials_path=credentials_path,
            allowed_extensions=allowed_extensions,
            max_file_size_bytes=max_file_size_bytes,
        )


def _http_status_name(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:  # pragma: no cover - defensive default
        return "Error"


def _normalize_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


async def _copy_to_tempfile(
    upload_file: UploadFile, max_bytes: Optional[int]
) -> Tuple["SpooledTemporaryFile", int]:
    from tempfile import SpooledTemporaryFile

    temp_file = SpooledTemporaryFile(
        max_size=max_bytes or (CHUNK_SIZE * 5), mode="w+b"
    )
    total_read = 0

    try:
        while True:
            chunk = await upload_file.read(CHUNK_SIZE)
            if not chunk:
                break

            total_read += len(chunk)
            if max_bytes is not None and total_read > max_bytes:
                temp_file.close()
                raise HTTPException(
                    status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploaded file exceeds the configured maximum size.",
                )

            temp_file.write(chunk)
    finally:
        await upload_file.close()

    temp_file.seek(0)
    return temp_file, total_read


def create_app() -> FastAPI:
    settings = Settings.from_env()

    from functools import lru_cache

    @lru_cache(maxsize=1)
    def get_bucket() -> storage.Bucket:
        client = storage.Client.from_service_account_json(
            str(settings.credentials_path)
        )
        return client.bucket(settings.bucket)

    app = FastAPI(title="GCP Uploader Proxy", version="2.0.0")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        name = _http_status_name(exc.status_code)
        description = exc.detail if isinstance(exc.detail, str) else name
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "name": name,
                "description": description,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": HTTP_500_INTERNAL_SERVER_ERROR,
                "name": _http_status_name(HTTP_500_INTERNAL_SERVER_ERROR),
                "description": "Unexpected internal server error.",
            },
        )

    @app.get("/healthz")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/upload")
    async def upload_file(request: Request, file: UploadFile = File(...)) -> JSONResponse:
        if not file.filename:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="A filename must be supplied.",
            )

        extension = _normalize_extension(file.filename)
        if settings.allowed_extensions and (
            not extension or extension not in settings.allowed_extensions
        ):
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="File type is not allowed.",
            )

        if settings.max_file_size_bytes is not None:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > settings.max_file_size_bytes:
                        raise HTTPException(
                            status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="Uploaded file exceeds the configured maximum size.",
                        )
                except ValueError:
                    # Ignore invalid content-length headers and fall back to streaming
                    pass

        content_type = file.content_type
        temp_file, total_read = await _copy_to_tempfile(
            file, settings.max_file_size_bytes
        )

        blob_name = f"{secrets.token_urlsafe(32)}{extension}"
        bucket = get_bucket()
        blob = bucket.blob(blob_name)

        try:
            blob.upload_from_file(temp_file, size=total_read, content_type=content_type)
            blob.make_public()
        except gcloud_exceptions.GoogleCloudError as exc:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to Google Cloud Storage.",
            ) from exc
        finally:
            temp_file.close()

        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "name": "Success",
                "description": blob.public_url,
            },
        )

    return app


app = create_app()

