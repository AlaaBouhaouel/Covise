from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0047_experience_date_to_charfield"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="requires_intro_post",
            field=models.BooleanField(default=False),
        ),
    ]
