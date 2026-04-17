from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0030_conversationuserstate"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="recording_mode",
            field=models.CharField(
                choices=[("recorded", "Recorded"), ("ephemeral", "Ephemeral")],
                default="recorded",
                max_length=20,
            ),
        ),
    ]
