from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """The NYS split becomes additive: full-time (top-up) plus part-time
    (subsidy-only, cost R0) counts, replacing count-plus-subset semantics.
    Defaults follow Jim's 2026-07-28 settings; the contribution moves to the
    new government round's R1,400."""

    dependencies = [
        ("api", "0044_fundingpot_is_ringfenced"),
    ]

    operations = [
        migrations.RenameField(
            model_name="budgetscenario",
            old_name="nys_conversion_count",
            new_name="nys_full_time_count",
        ),
        migrations.RenameField(
            model_name="budgetscenario",
            old_name="nys_subsidy_only_count",
            new_name="nys_part_time_count",
        ),
        migrations.AlterField(
            model_name="budgetscenario",
            name="nys_full_time_count",
            field=models.IntegerField(default=160),
        ),
        migrations.AlterField(
            model_name="budgetscenario",
            name="nys_part_time_count",
            field=models.IntegerField(default=40),
        ),
        migrations.AlterField(
            model_name="budgetscenario",
            name="subsidy_contribution",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1400"),
                max_digits=8,
            ),
        ),
    ]
