from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0004_waitlistemailverification"),
    ]

    operations = [
        migrations.AddField(
            model_name="waitlistemailverification",
            name="verification_code",
            field=models.CharField(blank=True, max_length=6),
        ),
    ]
