from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SubsidySchemeMigrationTests(TransactionTestCase):
    migrate_from = ("api", "0047_budgetscenario_last_paid_programme_date")
    migrate_to = ("api", "0048_budgetscenario_subsidy_schemes")

    def test_existing_nys_values_are_preserved_and_sef_is_not_activated(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        OldBudgetScenario = old_apps.get_model("api", "BudgetScenario")
        OldBudgetScenario.objects.create(
            year=2026,
            subsidy_contribution=Decimal("1900"),
            nys_full_time_count=127,
            nys_part_time_count=41,
            nys_conversion_start_month=9,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps
        BudgetScenario = new_apps.get_model("api", "BudgetScenario")
        scenario = BudgetScenario.objects.get(year=2026)

        self.assertEqual(
            scenario.nys_subsidy_contribution,
            Decimal("1900"),
        )
        self.assertEqual(scenario.nys_start_date, date(2026, 9, 1))
        self.assertEqual(scenario.nys_end_date, date(2026, 12, 31))
        self.assertEqual(scenario.sef_full_time_count, 0)
        self.assertEqual(scenario.sef_part_time_count, 0)
        self.assertEqual(scenario.sef_start_date, date(2026, 10, 1))
        self.assertEqual(scenario.sef_end_date, date(2027, 3, 31))
