from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import FundingPot, School


# (funder_name, amount, note, restricted school names, is_ringfenced). Empty
# schools tuple = unrestricted. Wind-farm pots are rural funders whose amounts
# Jim still has to confirm; seeding them at R0 with their school restrictions
# makes the segregated projection visible immediately.
POTS = (
    ("Winds of Change Community Trust", Decimal("0"), "", (), False),
    ("GWP: Children & Youth", Decimal("195930.47"), "", (), False),
    ("TDH: Exchange Rate Gains & Interest", Decimal("54065.15"), "", (), False),
    ("TDH: 2026 (April - December 2026)", Decimal("610310.80"), "", (), False),
    ("DGMT", Decimal("325000.00"), "", (), False),
    (
        "United Through Sport",
        Decimal("138471.54"),
        "",
        ("Astra", "Isaac Booi", "Green Apple", "Noluthando"),
        False,
    ),
    ("HCI", Decimal("200000.00"), "Fungible for youth or mentors", (), False),
    ("Yard Education Trust", Decimal("0"), "", (), False),
    (
        "Kouga Wind Farm",
        Decimal("0"),
        "Rural funder - amount to be confirmed",
        ("Sandwater", "Living Ubuntu", "Kokkewiet"),
        True,
    ),
    (
        "Tsitsikamma Wind Farm",
        Decimal("0"),
        "Rural funder - amount to be confirmed",
        # Vukani = Vukani Daycare (Jim confirmed 2026-07-28). Msobomvu Full
        # Service moved to Amakhala (Jim: the Tsitsikamma listing was a mistake).
        ("Bambino", "Clarkson", "Vukani Daycare", "Siyazama"),
        True,
    ),
    (
        "Amakhala Emoyeni Wind Farm",
        Decimal("0"),
        "Rural funder - amount to be confirmed",
        # Jim's corrected list (2026-07-28): Msobomvu Full Service, Msobomvu
        # ECD (= Msobomvu Preschool row), Mzamomhle ECD, Lingelethu Full
        # Service, Nced'uluntu ECD.
        (
            "Msobomvu Full Service",
            "Msobomvu Preschool",
            "Mzamomhle Edu-care",
            "Lingelethu",
            "Nceduluntu Edu-care",
        ),
        True,
    ),
)


class Command(BaseCommand):
    help = "Seed the known 2026 youth Funding Pots (idempotent)"

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        for funder_name, amount, note, school_names, is_ringfenced in POTS:
            pot, created = FundingPot.objects.get_or_create(
                year=2026,
                funder_name=funder_name,
                defaults={
                    "amount": amount,
                    "as_of": date(2026, 7, 27),
                    "note": note,
                    "is_active": True,
                    # Like school restrictions, the ringfenced policy is only
                    # asserted on create so later UI edits survive re-runs.
                    "is_ringfenced": is_ringfenced,
                },
            )
            created_count += int(created)
            # Restrictions are asserted only on create so later UI edits to a
            # pot's school list survive seed re-runs.
            if not created or not school_names:
                continue
            restricted = []
            for name in school_names:
                school = (
                    School.objects.filter(name__iexact=name)
                    .order_by("-is_active", "id")
                    .first()
                )
                if school is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"School not found for {funder_name}: {name}"
                        )
                    )
                else:
                    restricted.append(school)
            pot.schools.set(restricted)

        self.stdout.write(
            self.style.SUCCESS(
                f"Funding Pots ready: {len(POTS)} total, {created_count} created"
            )
        )
