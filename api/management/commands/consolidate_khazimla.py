"""One-off: consolidate the duplicate "Khazimla" school row onto the canonical
"Khazimla Pre-School" (SCH-00208), then retire the duplicate.

Background (2026-06-20): prod carried two rows for one educare -- the Airtable-
canonical "Khazimla Pre-School" (SCH-00208) and a legacy "Khazimla" row that held
SCH-00248 (a uid that does not exist in Airtable). The grid + both seeds had been
pointed at SCH-00248; Jim confirmed they are the SAME site, so the seed maps now
point at SCH-00208 and this command folds the duplicate's human-entered values
onto the canonical row and deletes it.

Moves only human-owned values (children_count on manual cells, youth_planned) and
only where the canonical cell is still empty, so a value the cron/seed already
wrote is never clobbered. A duplicate cell for a programme the canonical lacks is
re-pointed rather than dropped. Idempotent (a no-op once the duplicate is gone);
--dry-run prints the plan.

Run on Render (after seed_children_served, which fills the canonical 1000 Stories
cell):  python manage.py consolidate_khazimla --dry-run
        python manage.py consolidate_khazimla
"""
from django.core.management.base import BaseCommand
from django.db import transaction

CANONICAL_UID = "SCH-00208"     # "Khazimla Pre-School"
DUP_NAME = "Khazimla"           # the legacy row to retire (carried SCH-00248, now null)
HUMAN_FIELDS = ("youth_planned",)  # plus manual children_count, handled explicitly


class Command(BaseCommand):
    help = "Consolidate the duplicate 'Khazimla' row onto 'Khazimla Pre-School' (SCH-00208)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing.")

    def handle(self, *args, **options):
        from api.models import School, SchoolProgrammeYear

        canonical = School.objects.filter(school_uid=CANONICAL_UID).first()
        if canonical is None:
            self.stdout.write(self.style.ERROR(f"Canonical {CANONICAL_UID} not found; aborting."))
            return
        dups = list(School.objects.filter(name__iexact=DUP_NAME).exclude(pk=canonical.pk))
        if not dups:
            self.stdout.write(self.style.NOTICE("No duplicate 'Khazimla' row -- already consolidated."))
            return
        if len(dups) > 1:
            self.stdout.write(self.style.ERROR(
                f"Expected one duplicate, found {len(dups)} ({[d.id for d in dups]}); aborting for review."))
            return
        dup = dups[0]

        canon_cells = {
            (c.programme, c.year): c
            for c in SchoolProgrammeYear.objects.filter(school=canonical)
        }
        copies = []    # (target_cell, {field: value})
        repoints = []  # dup cells with no canonical counterpart -> move to canonical
        moves = []     # human-readable plan lines
        for cell in SchoolProgrammeYear.objects.filter(school=dup):
            target = canon_cells.get((cell.programme, cell.year))
            if target is None:
                repoints.append(cell)
                moves.append(f"  re-point {cell.programme} {cell.year} cell -> canonical (no existing cell)")
                continue
            fields = {}
            if cell.youth_planned is not None and target.youth_planned is None:
                fields["youth_planned"] = cell.youth_planned
            if (cell.count_source == "manual" and cell.children_count is not None
                    and target.children_count is None):
                fields["children_count"] = cell.children_count
            if fields:
                copies.append((target, fields))
                moves.append(f"  {cell.programme} {cell.year}: copy "
                             f"{', '.join(f'{k}={v}' for k, v in fields.items())} onto canonical")

        self.stdout.write(
            f"Consolidate '{dup.name}' (id {dup.id}) -> '{canonical.name}' (id {canonical.id}, {CANONICAL_UID}):")
        for line in moves or ["  (no human values to move)"]:
            self.stdout.write(line)
        self.stdout.write(f"  then DELETE School id {dup.id} (cascades its remaining grid cells/stats)")

        if options["dry_run"]:
            self.stdout.write(self.style.NOTICE("Dry run -- nothing written."))
            return

        with transaction.atomic():
            for cell in repoints:
                cell.school = canonical
                cell.save(update_fields=["school"])
            for target, fields in copies:
                for field, value in fields.items():
                    setattr(target, field, value)
                target.save(update_fields=list(fields) + ["updated_at"])
            dup.delete()
        self.stdout.write(self.style.SUCCESS(f"Done. Consolidated and retired id {dup.id}."))
