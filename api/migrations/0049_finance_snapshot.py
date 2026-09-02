# api/migrations/0049_finance_snapshot.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0048_budgetscenario_subsidy_schemes"),
    ]

    operations = [
        migrations.CreateModel(
            name="FinanceSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accounting_year", models.IntegerField(unique=True)),
                ("schema_version", models.CharField(max_length=16)),
                ("run_id", models.CharField(max_length=64)),
                ("workbook_name", models.CharField(max_length=255)),
                ("workbook_date", models.DateField(help_text="YYYYMMDD prefix of the source workbook; first anti-rollback key")),
                ("workbook_modified_at", models.DateTimeField(help_text="The workbook file's mtime when published; second anti-rollback key")),
                ("workbook_sha256", models.CharField(max_length=64)),
                ("payload_sha256", models.CharField(help_text="Canonical digest of the figures; the same-workbook idempotence key", max_length=64)),
                ("published_at", models.DateTimeField(help_text="When masi-finance produced the artifact")),
                ("payload", models.JSONField(default=dict)),
                ("loaded_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Finance Snapshot",
                "verbose_name_plural": "Finance Snapshots",
            },
        ),
    ]
