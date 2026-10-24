from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_pin_hash_plain'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='pin_failed_attempts',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='user',
            name='pin_locked_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
