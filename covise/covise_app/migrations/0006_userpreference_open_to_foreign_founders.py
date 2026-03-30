from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("covise_app", "0005_profile_referral_code_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreference",
            name="open_to_foreign_founders",
            field=models.BooleanField(default=True),
        ),
    ]
