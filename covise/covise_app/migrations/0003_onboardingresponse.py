from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('covise_app', '0002_waitlistentry_cv'),
    ]

    operations = [
        migrations.CreateModel(
            name='OnboardingResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('flow_name', models.CharField(blank=True, max_length=200)),
                ('answers', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('waitlist_entry', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='onboarding_responses', to='covise_app.waitlistentry')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
