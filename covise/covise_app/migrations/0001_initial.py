from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='WaitlistEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('full_name', models.CharField(max_length=150)),
                ('phone_number', models.CharField(max_length=30)),
                ('email', models.EmailField(max_length=254)),
                ('country', models.CharField(blank=True, max_length=100)),
                ('non_gcc_business', models.BooleanField(default=False)),
                ('custom_country', models.CharField(blank=True, max_length=100)),
                ('linkedin', models.URLField(max_length=300)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
