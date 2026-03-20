from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0006_waitlistentry_my_referral_code_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="waitlistentry",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("activated", "Activated"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
