# Generated by Django 5.2 on 2025-04-14 13:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idea', '0002_alter_lobby_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='lobby',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
