from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("covise_app", "0007_privateprofilecompletion"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="privateprofilecompletion",
            name="token",
        ),
        migrations.RemoveField(
            model_name="privateprofilecompletion",
            name="is_submitted",
        ),
        migrations.AddField(
            model_name="privateprofilecompletion",
            name="email",
            field=models.EmailField(default="", max_length=254, unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="privateprofilecompletion",
            name="full_name",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name="privateprofilecompletion",
            name="linkedin_url",
            field=models.URLField(max_length=300),
        ),
        migrations.AlterField(
            model_name="privateprofilecompletion",
            name="submitted_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="privateprofilecompletion",
            name="venture_summary",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterModelOptions(
            name="privateprofilecompletion",
            options={"ordering": ["-submitted_at"]},
        ),
    ]
