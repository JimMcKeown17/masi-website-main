import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0046_airtable_sync_cursor"),
    ]

    operations = [
        migrations.AddField(
            model_name="budgetscenario",
            name="last_paid_programme_date",
            field=models.DateField(default=datetime.date(2026, 11, 30)),
        ),
    ]
