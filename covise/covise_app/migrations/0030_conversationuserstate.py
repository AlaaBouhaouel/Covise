from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0029_notification"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConversationUserState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mute_notifications", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_states", to="covise_app.conversation")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conversation_states", to="covise_app.user")),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name="conversationuserstate",
            constraint=models.UniqueConstraint(fields=("conversation", "user"), name="unique_conversation_user_state"),
        ),
    ]
