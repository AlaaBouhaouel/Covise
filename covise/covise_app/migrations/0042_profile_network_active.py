from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('covise_app', '0041_datadeletionrequest_notes_profile_account_paused_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='network_active',
            field=models.BooleanField(default=False),
        ),
    ]
