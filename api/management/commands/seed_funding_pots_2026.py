from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import FundingPot, School


POTS = (
    ("Winds of Change Community Trust", Decimal("0"), ""),
    ("GWP: Children & Youth", Decimal("195930.47"), ""),
    (
        "TDH: Exchange Rate Gains & Interest",
        Decimal("54065.15"),
        "",
    ),
    (
        "TDH: 2026 (April - December 2026)",
        Decimal("610310.80"),
        "",
    ),
    ("DGMT", Decimal("325000.00"), ""),
    ("United Through Sport", Decimal("138471.54"), ""),
    (
        "HCI",
        Decimal("200000.00"),
        "Fungible for youth or mentors",
    ),
    ("Yard Education Trust", Decimal("0"), ""),
)
RESTRICTED_SCHOOLS = (
    "Astra",
    "Isaac Booi",
    "Green Apple",
    "Noluthando",
)


class Command(BaseCommand):
    help = "Seed the eight known 2026 youth Funding Pots"

    @transaction.atomic
    def handle(self, *args, **options):
        pots = {}
        created_count = 0
        for funder_name, amount, note in POTS:
            pot, created = FundingPot.objects.get_or_create(
                year=2026,
                funder_name=funder_name,
                defaults={
                    "amount": amount,
                    "as_of": date(2026, 7, 27),
                    "note": note,
                    "is_active": True,
                },
            )
            pots[funder_name] = pot
            created_count += int(created)

        restricted = []
        for name in RESTRICTED_SCHOOLS:
            school = (
                School.objects.filter(name__iexact=name)
                .order_by("-is_active", "id")
                .first()
            )
            if school is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"School not found for United Through Sport: {name}"
                    )
                )
            else:
                restricted.append(school)
        pots["United Through Sport"].schools.set(restricted)

        self.stdout.write(
            self.style.SUCCESS(
                f"Funding Pots ready: {len(POTS)} total, {created_count} created"
            )
        )
