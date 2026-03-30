from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("covise_app", "0007_userpreference_additional_settings_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="waitlistentry",
            name="my_referral_code",
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
