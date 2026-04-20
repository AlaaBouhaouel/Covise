from django.db import migrations, models

import covise_app.storage


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0043_profile_image_s3_storage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="attachment_file",
            field=models.FileField(
                blank=True,
                null=True,
                storage=covise_app.storage.PostImageStorage(),
                upload_to="chat_media/",
            ),
        ),
    ]
