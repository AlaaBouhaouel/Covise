from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0036_postimage"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="post",
            options={"ordering": ["-created_at"]},
        ),
        migrations.AlterModelOptions(
            name="comment",
            options={"ordering": ["created_at"]},
        ),
        migrations.AddField(
            model_name="comment",
            name="edited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="comment",
            name="is_pinned",
            field=models.BooleanField(default=False),
        ),
        migrations.RemoveConstraint(
            model_name="commentreaction",
            name="unique_user_comment_reaction",
        ),
        migrations.AddConstraint(
            model_name="commentreaction",
            constraint=models.UniqueConstraint(fields=("user", "comment", "reaction"), name="unique_user_comment_reaction"),
        ),
        migrations.CreateModel(
            name="MessageReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reaction", models.CharField(choices=[("thumbs_up", "Thumbs up"), ("fire", "Fire")], max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="covise_app.message")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="message_reactions", to="covise_app.user")),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="PostMention",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("handle_text", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("mentioned_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="post_mentions", to="covise_app.user")),
                ("post", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mentions", to="covise_app.post")),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="messagereaction",
            constraint=models.UniqueConstraint(fields=("user", "message", "reaction"), name="unique_user_message_reaction"),
        ),
        migrations.AddConstraint(
            model_name="postmention",
            constraint=models.UniqueConstraint(fields=("post", "mentioned_user", "handle_text"), name="unique_post_mention"),
        ),
    ]
