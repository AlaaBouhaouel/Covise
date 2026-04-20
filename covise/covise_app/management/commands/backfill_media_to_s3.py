import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from covise_app.models import Message, Post, PostImage, Profile
from covise_app.storage import post_image_storage


def _iter_media_fields():
    for profile in Profile.objects.exclude(profile_image="").exclude(profile_image__isnull=True).only("id", "profile_image"):
        yield "profile", profile.id, profile.profile_image

    for post in Post.objects.exclude(image="").exclude(image__isnull=True).only("id", "image"):
        yield "post", post.id, post.image

    for image in PostImage.objects.exclude(image="").exclude(image__isnull=True).only("id", "image"):
        yield "post_gallery", image.id, image.image

    for message in Message.objects.exclude(attachment_file="").exclude(attachment_file__isnull=True).only("id", "attachment_file"):
        yield "message_attachment", message.id, message.attachment_file


class Command(BaseCommand):
    help = "Upload existing local media files to the configured S3 bucket using their current storage keys."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be uploaded without changing S3.",
        )

    def handle(self, *args, **options):
        if not post_image_storage._use_s3():
            raise CommandError(
                "S3 media storage is not active. Check DEBUG/AWS_* settings before backfilling media."
            )

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        dry_run = bool(options.get("dry_run"))
        s3_client = post_image_storage._s3_client()
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        uploaded_count = 0
        skipped_existing_count = 0
        missing_local_count = 0

        self.stdout.write(self.style.MIGRATE_HEADING(f"Backfilling media to s3://{bucket_name}"))

        for label, object_id, field_file in _iter_media_fields():
            key = post_image_storage._normalize_name(getattr(field_file, "name", ""))
            if not key:
                continue

            local_path = media_root / key
            if not local_path.exists():
                missing_local_count += 1
                self.stdout.write(
                    self.style.WARNING(f"Missing local file for {label}:{object_id} -> {key}")
                )
                continue

            if dry_run:
                self.stdout.write(f"Would upload: {label}:{object_id} -> {key}")
                continue

            if post_image_storage.exists(key):
                skipped_existing_count += 1
                self.stdout.write(f"Already in S3: {label}:{object_id} -> {key}")
                continue

            content_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"

            with local_path.open("rb") as handle:
                s3_client.upload_fileobj(
                    handle,
                    bucket_name,
                    key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "ServerSideEncryption": "AES256",
                    },
                )
            uploaded_count += 1
            self.stdout.write(self.style.SUCCESS(f"Uploaded: {label}:{object_id} -> {key}"))

        self.stdout.write("")
        self.stdout.write(f"Uploaded: {uploaded_count}")
        self.stdout.write(f"Already present: {skipped_existing_count}")
        self.stdout.write(f"Missing locally: {missing_local_count}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only. No files were uploaded."))
