from django.contrib.auth.hashers import identify_hasher
from django.core.management.base import BaseCommand

from covise_app.models import User, WaitlistEntry


def _is_mixed_case_email(email):
    value = str(email or "").strip()
    return bool(value) and value != value.lower()


def _password_looks_like_django_hash(encoded_password):
    value = str(encoded_password or "").strip()
    if not value:
        return False
    try:
        identify_hasher(value)
    except Exception:
        return False
    return True


class Command(BaseCommand):
    help = "Audit auth-related data for mixed-case emails and invalid password hashes."

    def handle(self, *args, **options):
        mixed_case_users = []
        invalid_password_users = []
        mixed_case_waitlist = []

        for user in User.objects.all().only("id", "email", "password"):
            if _is_mixed_case_email(user.email):
                mixed_case_users.append(user)
            if not _password_looks_like_django_hash(user.password):
                invalid_password_users.append(user)

        for entry in WaitlistEntry.objects.all().only("id", "email", "status"):
            if _is_mixed_case_email(entry.email):
                mixed_case_waitlist.append(entry)

        self.stdout.write(self.style.MIGRATE_HEADING("Auth data audit"))
        self.stdout.write(f"Users with mixed-case email: {len(mixed_case_users)}")
        self.stdout.write(f"Users with invalid password hash: {len(invalid_password_users)}")
        self.stdout.write(f"Waitlist entries with mixed-case email: {len(mixed_case_waitlist)}")

        if mixed_case_users:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Mixed-case user emails"))
            for user in mixed_case_users[:20]:
                self.stdout.write(f"- {user.id} | {user.email}")

        if invalid_password_users:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Users with non-Django password values"))
            for user in invalid_password_users[:20]:
                preview = str(user.password or "")[:20]
                self.stdout.write(f"- {user.id} | {user.email} | password_prefix={preview}")

        if mixed_case_waitlist:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Mixed-case waitlist emails"))
            for entry in mixed_case_waitlist[:20]:
                self.stdout.write(f"- {entry.id} | {entry.email} | status={entry.status}")

        if not mixed_case_users and not invalid_password_users and not mixed_case_waitlist:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("No auth data issues found."))
