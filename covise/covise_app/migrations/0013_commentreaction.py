from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0012_comment_down_comment_up"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommentReaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reaction", models.CharField(choices=[("up", "Upvote"), ("down", "Downvote")], max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("comment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reactions", to="covise_app.comment")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comment_reactions", to="covise_app.user")),
            ],
        ),
        migrations.AddConstraint(
            model_name="commentreaction",
            constraint=models.UniqueConstraint(fields=("user", "comment"), name="unique_user_comment_reaction"),
        ),
    ]
