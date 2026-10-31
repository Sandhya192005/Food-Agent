import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.exceptions import StorageError
from app.services.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """Keeps photos in a private S3 bucket. The browser gets them through presigned
    URLs: signed links that work for a few minutes, so the bucket never goes public."""

    name = "s3"

    def __init__(self, bucket: str | None = None, client=None) -> None:
        self.bucket = bucket or settings.S3_BUCKET_NAME
        self.client = client or boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            # The regional address (not the global s3.amazonaws.com), so presigned
            # links are checked against the bucket's own region and don't fail.
            endpoint_url=f"https://s3.{settings.AWS_REGION}.amazonaws.com",
            # Empty strings mean "not set": let boto3 find credentials itself.
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
            # Signature v4 is required for presigned URLs in newer regions.
            # Bucket name in the host: <bucket>.s3.<region>.amazonaws.com
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )

    def save(
        self, content: bytes, filename: str, *, folder: str = "", content_type: str | None = None
    ) -> str:
        suffix = Path(filename).suffix.lower() or ".jpg"
        key = f"{folder.strip('/')}/{uuid.uuid4().hex}{suffix}".lstrip("/")
        extra = {"ContentType": content_type} if content_type else {}
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content, **extra)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Couldn't upload the photo to S3: {exc}") from exc
        return key

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"Couldn't delete the photo from S3: {exc}") from exc

    def read(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                raise FileNotFoundError(key) from exc
            raise StorageError(f"Couldn't read the photo from S3: {exc}") from exc
        except BotoCoreError as exc:
            raise StorageError(f"Couldn't read the photo from S3: {exc}") from exc

    def url_for(self, key: str) -> str | None:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
            )
        except (BotoCoreError, ClientError):
            # The details page still works; the browser falls back to GET /meals/{id}/image.
            return None
