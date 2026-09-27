import hashlib
import os
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.client import Config

from app.config import settings


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class StorageService:
    def __init__(self) -> None:
        self._use_s3 = bool(settings.s3_endpoint_url)
        if self._use_s3:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
                config=Config(signature_version="s3v4"),
            )
        else:
            Path(settings.local_upload_dir).mkdir(parents=True, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return "s3" if self._use_s3 else "filesystem"

    def put_immutable(self, organization_id: str, filename: str, data: bytes) -> tuple[str, str]:
        digest = sha256_hex(data)
        ext = Path(filename).suffix or ".bin"
        key = f"{organization_id}/{digest}/{uuid4()}{ext}"

        if self._use_s3:
            self._client.put_object(
                Bucket=settings.s3_bucket,
                Key=key,
                Body=data,
                ContentType="application/octet-stream",
                Metadata={"sha256": digest},
            )
        else:
            path = Path(settings.local_upload_dir) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        return key, digest


storage_service = StorageService()
