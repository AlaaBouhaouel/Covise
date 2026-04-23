from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('covise_app', '0049_post_is_pinned'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='post',
            name='is_pinned',
        ),
        migrations.CreateModel(
            name='UserPinnedPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pinned_by_users', to='covise_app.post')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pinned_post', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=['user'], name='one_pin_per_user')],
            },
        ),
    ]
