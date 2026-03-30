from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0002_alter_onboardingresponse_waitlist_entry_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="github",
            field=models.URLField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="profile",
            name="nationality",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="profile",
            name="onboarding_answers",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="profile",
            name="plan",
            field=models.CharField(default="Free", max_length=50),
        ),
        migrations.AddField(
            model_name="profile",
            name="proof_of_work_url",
            field=models.URLField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="profile",
            name="tools",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="waitlist_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
