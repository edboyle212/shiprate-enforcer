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

    def _etl_root(self) -> Path:
        return Path(settings.local_upload_dir) / settings.etl_drop_root

    def list_etl_objects(self, partner_id: str, organization_id: str, subfolder: str) -> list[str]:
        """Relative keys under etl-drops/{partner}/{org}/{subfolder}/."""
        prefix = f"{settings.etl_drop_root}/{partner_id}/{organization_id}/{subfolder}"
        if self._use_s3:
            keys: list[str] = []
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix=f"{prefix}/"):
                for obj in page.get("Contents") or []:
                    keys.append(obj["Key"])
            return keys
        base = self._etl_root() / partner_id / organization_id / subfolder
        if not base.is_dir():
            return []
        return [f"{prefix}/{p.name}" for p in base.iterdir() if p.is_file()]

    def read_object(self, key: str) -> bytes:
        if self._use_s3:
            resp = self._client.get_object(Bucket=settings.s3_bucket, Key=key)
            return resp["Body"].read()
        path = Path(settings.local_upload_dir) / key
        return path.read_bytes()


storage_service = StorageService()
