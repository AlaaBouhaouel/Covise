from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('covise_app', '0048_profile_requires_intro_post'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='is_pinned',
            field=models.BooleanField(default=False),
        ),
    ]
