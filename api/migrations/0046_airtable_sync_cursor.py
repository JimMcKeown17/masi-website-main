from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0045_nys_additive_split"),
    ]

    operations = [
        migrations.CreateModel(
            name="AirtableSyncCursor",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sync_type", models.CharField(max_length=50, unique=True, verbose_name="Sync Type")),
                (
                    "created_through",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Airtable Records Created Through",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Airtable Sync Cursor",
                "verbose_name_plural": "Airtable Sync Cursors",
            },
        ),
    ]
