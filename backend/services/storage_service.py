from __future__ import annotations

import base64
import mimetypes

import boto3
from botocore.exceptions import ClientError

from config import get_settings


class StorageService:
    def __init__(self) -> None:
        s = get_settings()
        self._bucket = s.supabase_storage_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=s.supabase_s3_endpoint,
            aws_access_key_id=s.supabase_s3_access_key,
            aws_secret_access_key=s.supabase_s3_secret_key,
            region_name=s.supabase_s3_region,
        )

    def upload(self, claim_id: str, file_id: str, content: bytes, mime: str) -> str:
        ext = (mimetypes.guess_extension(mime) or ".bin").lstrip(".")
        key = f"{claim_id}/{file_id}.{ext}"
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=mime)
        return key

    def download_b64(self, key: str) -> str:
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return base64.b64encode(resp["Body"].read()).decode()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presigned_url(self, key: str, expiry: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expiry,
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self._client.create_bucket(Bucket=self._bucket)
            else:
                raise