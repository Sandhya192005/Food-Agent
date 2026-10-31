"""S3Storage against moto's fake S3: no AWS account or network needed."""

import boto3
import pytest
from moto import mock_aws

from app.core.exceptions import StorageError
from app.services.storage.s3 import S3Storage

BUCKET = "food-agent-test-photos"
REGION = "ap-south-1"


@pytest.fixture()
def s3(monkeypatch):
    # Fake credentials, so a real ~/.aws profile can never be used by accident.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION}
        )
        yield S3Storage(bucket=BUCKET, client=client), client


def test_save_uploads_object_and_returns_key(s3):
    storage, client = s3
    key = storage.save(
        b"photo-bytes", "lunch.JPG", folder="meals/user-7", content_type="image/jpeg"
    )

    assert key.startswith("meals/user-7/")
    assert key.endswith(".jpg")
    obj = client.get_object(Bucket=BUCKET, Key=key)
    assert obj["Body"].read() == b"photo-bytes"
    assert obj["ContentType"] == "image/jpeg"


def test_read_returns_bytes_and_missing_key_raises_file_not_found(s3):
    storage, _ = s3
    key = storage.save(b"abc", "a.png")
    assert storage.read(key) == b"abc"
    with pytest.raises(FileNotFoundError):
        storage.read("meals/nope.jpg")


def test_delete_removes_object(s3):
    storage, client = s3
    key = storage.save(b"abc", "a.jpg")
    storage.delete(key)
    assert client.list_objects_v2(Bucket=BUCKET).get("KeyCount") == 0


def test_url_for_returns_presigned_link(s3):
    storage, _ = s3
    key = storage.save(b"abc", "a.jpg")
    url = storage.url_for(key)
    assert BUCKET in url and key in url
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=900" in url


def test_upload_to_missing_bucket_raises_storage_error(s3):
    _, client = s3
    storage = S3Storage(bucket="bucket-that-does-not-exist", client=client)
    with pytest.raises(StorageError):
        storage.save(b"abc", "a.jpg")
