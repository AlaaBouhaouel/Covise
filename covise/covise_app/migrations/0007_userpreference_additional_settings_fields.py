from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("covise_app", "0006_userpreference_open_to_foreign_founders"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreference",
            name="minimum_commitment",
            field=models.CharField(default="Either", max_length=20),
        ),
        migrations.AddField(
            model_name="userpreference",
            name="preferred_cofounder_types",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="userpreference",
            name="preferred_gcc_markets",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="userpreference",
            name="preferred_industries",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="userpreference",
            name="read_profile_data",
            field=models.BooleanField(default=True),
        ),
    ]
