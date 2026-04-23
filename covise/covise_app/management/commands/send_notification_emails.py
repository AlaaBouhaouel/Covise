from django.core.management.base import BaseCommand

from covise_app.models import Notification
from covise_app.notifications import mark_notification_email_processed, send_notification_email


class Command(BaseCommand):
    help = "Send queued notification emails for notifications that have not been processed yet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Maximum number of pending notifications to process in one run.",
        )

    def handle(self, *args, **options):
        limit = max(1, int(options.get("limit") or 200))
        pending_notifications = list(
            Notification.objects.filter(emailed_at__isnull=True)
            .select_related("recipient", "actor")
            .order_by("created_at")[:limit]
        )

        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for notification in pending_notifications:
            sent = send_notification_email(notification, mark_skipped=True)
            if sent:
                sent_count += 1
                continue
            if notification.emailed_at:
                skipped_count += 1
            else:
                failed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {len(pending_notifications)} pending notifications: "
                f"{sent_count} sent, {skipped_count} skipped, {failed_count} failed."
            )
        )
