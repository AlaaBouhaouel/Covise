import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0003_waitlistentry_form_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="WaitlistEmailVerification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
    ]
