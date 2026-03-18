import secrets
import string

import django.db.models.deletion
from django.db import migrations, models


def generate_unique_codes(apps, schema_editor):
    WaitlistEntry = apps.get_model('covise_app', 'WaitlistEntry')
    chars = string.ascii_uppercase + string.digits
    used = set()
    for entry in WaitlistEntry.objects.filter(my_referral_code=''):
        for _ in range(20):
            code = 'CV-' + ''.join(secrets.choice(chars) for _ in range(8))
            if code not in used:
                used.add(code)
                break
        entry.my_referral_code = code
        entry.save(update_fields=['my_referral_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('covise_app', '0005_alter_waitlistentry_email'),
    ]

    operations = [
        # Step 1 — add field without unique constraint so existing rows can be populated
        migrations.AddField(
            model_name='waitlistentry',
            name='my_referral_code',
            field=models.CharField(blank=True, max_length=20, default=''),
        ),
        # Step 2 — backfill existing rows with unique codes
        migrations.RunPython(generate_unique_codes, migrations.RunPython.noop),
        # Step 3 — now safe to add the unique constraint
        migrations.AlterField(
            model_name='waitlistentry',
            name='my_referral_code',
            field=models.CharField(blank=True, max_length=20, unique=True),
        ),
        # Step 4 — add referred_by FK
        migrations.AddField(
            model_name='waitlistentry',
            name='referred_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='referrals', to='covise_app.waitlistentry'),
        ),
    ]
