from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0045_postreaction"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="quote_color",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="post",
            name="quote_content",
            field=models.TextField(blank=True, default=""),
        ),
    ]
