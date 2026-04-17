from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0027_blockeduser"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="has_accepted_platform_agreement",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="profile",
            name="platform_agreement_accepted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="platform_agreement_version",
            field=models.CharField(default="2026.04", max_length=20),
        ),
    ]
