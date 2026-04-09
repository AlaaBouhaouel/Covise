from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0002_alter_onboardingresponse_waitlist_entry_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="waitlistentry",
            name="custom_description",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="waitlistentry",
            name="description",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="waitlistentry",
            name="no_linkedin",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="waitlistentry",
            name="venture_summary",
            field=models.TextField(blank=True),
        ),
    ]
