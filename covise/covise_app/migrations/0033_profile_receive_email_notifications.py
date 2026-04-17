from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0032_message_media_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="receive_email_notifications",
            field=models.BooleanField(default=True),
        ),
    ]
