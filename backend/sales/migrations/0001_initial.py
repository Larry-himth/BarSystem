# Generated migration
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalog', '0001_initial'),
        ('shifts', '0001_initial'),
        ('tabs', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('total', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('void_reason', models.TextField(blank=True)),
                ('voided_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('shift', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sales', to='shifts.shift')),
                ('voided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='sales_voided', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='SaleLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('qty', models.IntegerField()),
                ('unit_price', models.IntegerField()),
                ('line_total', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('item_unit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='catalog.itemunit')),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lines', to='sales.sale')),
            ],
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(choices=[('CASH', 'Cash'), ('MOMO', 'Mobile Money'), ('TAB', 'Tab')], max_length=16)),
                ('amount', models.IntegerField()),
                ('momo_ref', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payments', to='sales.sale')),
                ('tab', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='tabs.tab')),
            ],
        ),
    ]
