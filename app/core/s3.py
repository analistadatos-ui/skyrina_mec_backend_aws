"""
S3 upload helper.

Replaces the old local-disk writes (open(path, "wb")) that don't work on
Lambda. Files go to an S3 bucket; we store the object KEY in the database
and serve the image via CloudFront.

Required environment variables (set in Lambda config):
  UPLOADS_BUCKET   - name of the S3 bucket for uploads
  UPLOADS_CDN_BASE - (optional) CloudFront base URL, e.g. https://media.skyrina.com.mx
                     If set, public_url() returns CDN links; otherwise the S3 URL.

Lambda's execution role must allow s3:PutObject (and s3:GetObject if the
backend ever reads them) on this bucket. SAM/IAM handles that.
"""

import os
import uuid

import boto3

_s3 = boto3.client("s3")

UPLOADS_BUCKET = os.getenv("UPLOADS_BUCKET")
UPLOADS_CDN_BASE = os.getenv("UPLOADS_CDN_BASE", "").rstrip("/")


def upload_fileobj(file_obj, original_filename: str, prefix: str = "") -> str:
    """
    Upload a file-like object's BYTES to S3 and return the stored object key.

    `file_obj` here is the raw bytes already read from an UploadFile
    (i.e. pass `await upload.read()`), matching how the old code did
    `buffer.write(await image.read())`.

    `prefix` lets us keep folders like "validations/" inside the bucket,
    mirroring the old VALIDATION_FOLDER behaviour.
    """
    if not UPLOADS_BUCKET:
        raise RuntimeError("UPLOADS_BUCKET env var is not set")

    ext = ""
    if original_filename and "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[-1].lower()

    key = f"{prefix}{uuid.uuid4().hex}{ext}" if prefix else f"{uuid.uuid4().hex}{ext}"

    content_type = _guess_content_type(ext)

    _s3.put_object(
        Bucket=UPLOADS_BUCKET,
        Key=key,
        Body=file_obj,
        ContentType=content_type,
    )
    return key


def public_url(key: str) -> str:
    """Turn a stored S3 key into a URL the frontend can load."""
    if not key:
        return None
    if UPLOADS_CDN_BASE:
        return f"{UPLOADS_CDN_BASE}/{key}"
    region = os.getenv("AWS_REGION", "mx-central-1")
    return f"https://{UPLOADS_BUCKET}.s3.{region}.amazonaws.com/{key}"


def _guess_content_type(ext: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }.get(ext, "application/octet-stream")