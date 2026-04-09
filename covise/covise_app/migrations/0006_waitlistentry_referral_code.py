from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0005_waitlistemailverification_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="waitlistentry",
            name="referral_code",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
