from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0033_profile_receive_email_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="group_name",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="conversation_type",
            field=models.CharField(
                choices=[("private", "Private"), ("group", "Group")],
                default="private",
                max_length=20,
            ),
        ),
    ]
