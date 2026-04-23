import mimetypes
from io import BytesIO
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible
from PIL import Image, ImageOps, UnidentifiedImageError


@deconstructible
class PostImageStorage(Storage):
    """
    Store media on S3 in production while keeping local filesystem storage for
    development and any environment without valid AWS media settings.
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
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "virtual"},
            ),
        )

    def _normalize_name(self, name):
        return str(name or "").replace("\\", "/").lstrip("/")

    def _image_max_dimension(self, normalized_name):
        if normalized_name.startswith("profile_images/"):
            return max(256, int(getattr(settings, "PROFILE_IMAGE_MAX_DIMENSION", 768) or 768))
        if normalized_name.startswith("chat_media/"):
            return max(512, int(getattr(settings, "CHAT_IMAGE_MAX_DIMENSION", 1600) or 1600))
        return max(512, int(getattr(settings, "POST_IMAGE_MAX_DIMENSION", 1600) or 1600))

    def _cache_control(self, normalized_name):
        if normalized_name.startswith("chat_media/"):
            return str(getattr(settings, "AWS_S3_PRIVATE_MEDIA_CACHE_CONTROL", "private, max-age=3600") or "private, max-age=3600")
        return str(getattr(settings, "AWS_S3_PUBLIC_MEDIA_CACHE_CONTROL", "public, max-age=604800, stale-while-revalidate=86400") or "public, max-age=604800, stale-while-revalidate=86400")

    def _optimize_upload(self, normalized_name, content, content_type):
        guessed_content_type = content_type or mimetypes.guess_type(normalized_name)[0] or "application/octet-stream"
        if not guessed_content_type.startswith("image/"):
            if hasattr(content, "seek"):
                content.seek(0)
            return content, guessed_content_type

        if guessed_content_type in {"image/gif", "image/svg+xml"}:
            if hasattr(content, "seek"):
                content.seek(0)
            return content, guessed_content_type

        if hasattr(content, "seek"):
            content.seek(0)
        original_bytes = content.read()
        original_name = getattr(content, "name", normalized_name)
        if hasattr(content, "seek"):
            content.seek(0)
        if not original_bytes:
            return content, guessed_content_type

        try:
            image = Image.open(BytesIO(original_bytes))
            image = ImageOps.exif_transpose(image)
        except (UnidentifiedImageError, OSError, ValueError):
            return ContentFile(original_bytes, name=original_name), guessed_content_type

        original_width, original_height = image.size
        max_dimension = self._image_max_dimension(normalized_name)
        resized = False
        if max(original_width, original_height) > max_dimension:
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            resized = True

        image_format = (image.format or "").upper()
        save_kwargs = {}
        effective_content_type = guessed_content_type
        if image_format in {"JPEG", "JPG"} or guessed_content_type == "image/jpeg":
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image_format = "JPEG"
            effective_content_type = "image/jpeg"
            save_kwargs = {"quality": 82, "optimize": True, "progressive": True}
        elif image_format == "PNG" or guessed_content_type == "image/png":
            image_format = "PNG"
            effective_content_type = "image/png"
            save_kwargs = {"optimize": True, "compress_level": 9}
        elif image_format == "WEBP" or guessed_content_type == "image/webp":
            image_format = "WEBP"
            effective_content_type = "image/webp"
            save_kwargs = {"quality": 82, "method": 6}
        else:
            return ContentFile(original_bytes, name=original_name), guessed_content_type

        buffer = BytesIO()
        try:
            image.save(buffer, format=image_format, **save_kwargs)
        except OSError:
            return ContentFile(original_bytes, name=original_name), guessed_content_type

        optimized_bytes = buffer.getvalue()
        if not optimized_bytes:
            return ContentFile(original_bytes, name=original_name), guessed_content_type
        if not resized and len(optimized_bytes) >= len(original_bytes):
            return ContentFile(original_bytes, name=original_name), guessed_content_type
        return ContentFile(optimized_bytes, name=original_name), effective_content_type

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

    def _use_signed_urls(self):
        return bool(getattr(settings, "AWS_S3_MEDIA_USE_SIGNED_URLS", True))

    def _presigned_url_expiry(self):
        expiry = int(getattr(settings, "AWS_S3_MEDIA_URL_EXPIRY", 3600) or 3600)
        return max(60, expiry)

    def _s3_presigned_url(self, name):
        normalized_name = self._normalize_name(name)
        return self._s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": normalized_name,
            },
            ExpiresIn=self._presigned_url_expiry(),
        )

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
        upload_content, content_type = self._optimize_upload(normalized_name, content, content_type)
        extra_args = {
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
            "CacheControl": self._cache_control(normalized_name),
        }
        if hasattr(upload_content, "seek"):
            upload_content.seek(0)
        self._s3_client().upload_fileobj(
            upload_content,
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
        if self._use_signed_urls():
            return self._s3_presigned_url(normalized_name)
        return self._s3_url(normalized_name)


post_image_storage = PostImageStorage()
