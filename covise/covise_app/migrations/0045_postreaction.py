from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0044_message_attachment_s3_storage"),
    ]

    operations = [
        migrations.CreateModel(
            name="PostReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reaction", models.CharField(choices=[("thumbs_up", "Thumbs up"), ("thumbs_down", "Thumbs down")], max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="covise_app.post")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="post_reactions", to="covise_app.user")),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="postreaction",
            constraint=models.UniqueConstraint(fields=("user", "post"), name="unique_user_post_reaction"),
        ),
    ]
