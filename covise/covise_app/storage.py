import mimetypes
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class PostImageStorage(Storage):
    """
    Store post images on S3 in production while keeping local filesystem storage
    for development and any environment without valid AWS media settings.
    """

    def _use_s3(self):
        return bool(
            not settings.DEBUG
            and getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
            and getattr(settings, "AWS_ACCESS_KEY_ID", "")
            and getattr(settings, "AWS_SECRET_ACCESS_KEY", "")
        )

    def _local_storage(self):
        return FileSystemStorage(
            location=settings.MEDIA_ROOT,
            base_url=settings.MEDIA_URL,
        )

    def _s3_client(self):
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
        )

    def _normalize_name(self, name):
        return str(name or "").replace("\\", "/").lstrip("/")

    def _s3_url(self, name):
        normalized_name = self._normalize_name(name)
        base_url = str(getattr(settings, "AWS_S3_MEDIA_BASE_URL", "") or "").strip().rstrip("/")
        if base_url:
            return f"{base_url}/{quote(normalized_name)}"

        region = str(getattr(settings, "AWS_S3_REGION_NAME", "") or "").strip()
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        if not region or region == "us-east-1":
            return f"https://{bucket}.s3.amazonaws.com/{quote(normalized_name)}"
        return f"https://{bucket}.s3.{region}.amazonaws.com/{quote(normalized_name)}"

    def _open(self, name, mode="rb"):
        normalized_name = self._normalize_name(name)
        if not self._use_s3():
            return self._local_storage()._open(normalized_name, mode)

        response = self._s3_client().get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=normalized_name,
        )
        return ContentFile(response["Body"].read(), name=normalized_name)

    def _save(self, name, content):
        normalized_name = self._normalize_name(name)
        if not self._use_s3():
            return self._local_storage()._save(normalized_name, content)

        content_type = getattr(content, "content_type", "") or mimetypes.guess_type(normalized_name)[0] or "application/octet-stream"
        extra_args = {
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
        }
        if hasattr(content, "seek"):
            content.seek(0)
        self._s3_client().upload_fileobj(
            content,
            settings.AWS_STORAGE_BUCKET_NAME,
            normalized_name,
            ExtraArgs=extra_args,
        )
        return normalized_name

    def delete(self, name):
        normalized_name = self._normalize_name(name)
        if not normalized_name:
            return
        if not self._use_s3():
            return self._local_storage().delete(normalized_name)
        self._s3_client().delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=normalized_name,
        )

    def exists(self, name):
        normalized_name = self._normalize_name(name)
        if not self._use_s3():
            return self._local_storage().exists(normalized_name)
        try:
            self._s3_client().head_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=normalized_name,
            )
            return True
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def size(self, name):
        normalized_name = self._normalize_name(name)
        if not self._use_s3():
            return self._local_storage().size(normalized_name)
        response = self._s3_client().head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=normalized_name,
        )
        return int(response.get("ContentLength", 0))

    def url(self, name):
        normalized_name = self._normalize_name(name)
        if not self._use_s3():
            return self._local_storage().url(normalized_name)
        return self._s3_url(normalized_name)


post_image_storage = PostImageStorage()
