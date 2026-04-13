import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0006_waitlistentry_referral_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="PrivateProfileCompletion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("full_name", models.CharField(blank=True, max_length=150)),
                ("linkedin_url", models.URLField(blank=True, max_length=300)),
                ("venture_summary", models.CharField(blank=True, max_length=150)),
                ("is_submitted", models.BooleanField(default=False)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
