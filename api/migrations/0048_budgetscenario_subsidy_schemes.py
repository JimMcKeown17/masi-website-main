from datetime import date
from decimal import Decimal

from django.db import migrations, models


def populate_subsidy_schemes(apps, schema_editor):
    BudgetScenario = apps.get_model("api", "BudgetScenario")
    for scenario in BudgetScenario.objects.all().iterator():
        scenario.nys_subsidy_contribution = scenario.subsidy_contribution
        scenario.nys_start_date = date(
            scenario.year,
            scenario.nys_conversion_start_month,
            1,
        )
        scenario.nys_end_date = date(scenario.year, 12, 31)
        # Existing saved scenarios must not silently activate the proposed SEF
        # cohort. New scenarios receive the 200-person suggestion through the
        # API's year-aware defaults.
        scenario.sef_full_time_count = 0
        scenario.sef_start_date = date(scenario.year, 10, 1)
        scenario.sef_end_date = date(scenario.year + 1, 3, 31)
        scenario.save(
            update_fields=[
                "nys_subsidy_contribution",
                "nys_start_date",
                "nys_end_date",
                "sef_full_time_count",
                "sef_start_date",
                "sef_end_date",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0047_budgetscenario_last_paid_programme_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="budgetscenario",
            name="nys_subsidy_contribution",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=8,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="budgetscenario",
            name="nys_start_date",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="budgetscenario",
            name="nys_end_date",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="budgetscenario",
            name="sef_subsidy_contribution",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1400"),
                max_digits=8,
            ),
        ),
        migrations.AddField(
            model_name="budgetscenario",
            name="sef_full_time_count",
            field=models.IntegerField(default=200),
        ),
        migrations.AddField(
            model_name="budgetscenario",
            name="sef_part_time_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="budgetscenario",
            name="sef_start_date",
            field=models.DateField(null=True),
        ),
        migrations.AddField(
            model_name="budgetscenario",
            name="sef_end_date",
            field=models.DateField(null=True),
        ),
        migrations.RunPython(populate_subsidy_schemes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="budgetscenario",
            name="nys_subsidy_contribution",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1900"),
                max_digits=8,
            ),
        ),
        migrations.AlterField(
            model_name="budgetscenario",
            name="nys_start_date",
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name="budgetscenario",
            name="nys_end_date",
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name="budgetscenario",
            name="sef_start_date",
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name="budgetscenario",
            name="sef_end_date",
            field=models.DateField(),
        ),
    ]
