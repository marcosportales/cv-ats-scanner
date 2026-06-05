import hashlib
import uuid

import boto3
from botocore.client import Config

from app.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def upload_file(user_id: uuid.UUID, filename: str, content: bytes, mime_type: str) -> tuple[str, str]:
    client = get_s3_client()
    file_id = uuid.uuid4()
    key = f"users/{user_id}/resumes/{file_id}/{filename}"
    checksum = hashlib.sha256(content).hexdigest()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=content,
        ContentType=mime_type,
    )
    return key, checksum


def download_file(storage_key: str) -> bytes:
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket, Key=storage_key)
    return response["Body"].read()


def delete_file(storage_key: str) -> None:
    client = get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=storage_key)
