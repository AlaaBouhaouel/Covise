from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('covise_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='waitlistentry',
            name='cv',
            field=models.FileField(blank=True, null=True, upload_to='cv_uploads/'),
        ),
    ]
