from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0037_post_comment_message_features"),
    ]

    operations = [
        migrations.AlterField(
            model_name="commentreaction",
            name="reaction",
            field=models.CharField(
                choices=[
                    ("thumbs_up", "Thumbs up"),
                    ("thumbs_down", "Thumbs down"),
                    ("fire", "Fire"),
                    ("rocket", "Rocket"),
                    ("crazy", "Crazy"),
                ],
                max_length=20,
            ),
        ),
    ]
