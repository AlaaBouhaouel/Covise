from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0031_conversation_recording_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="attachment_content_type",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="message",
            name="attachment_file",
            field=models.FileField(blank=True, null=True, upload_to="chat_media/"),
        ),
        migrations.AddField(
            model_name="message",
            name="attachment_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="message",
            name="attachment_size",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="message",
            name="message_type",
            field=models.CharField(
                choices=[
                    ("text", "Text"),
                    ("image", "Image"),
                    ("file", "File"),
                    ("voice", "Voice"),
                ],
                default="text",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="message",
            name="body",
            field=models.TextField(blank=True, default=""),
        ),
    ]
