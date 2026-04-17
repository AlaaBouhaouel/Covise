from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0026_savedpost"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlockedUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("blocked", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocked_by_relationships", to="covise_app.user")),
                ("blocker", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocked_relationships", to="covise_app.user")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="blockeduser",
            constraint=models.UniqueConstraint(fields=("blocker", "blocked"), name="unique_user_block"),
        ),
    ]
