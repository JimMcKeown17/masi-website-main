from django.core.management.base import BaseCommand
from django.db.models import Q
from api.models import (
    LiteracySession2026, NumeracySession2026,
    Youth, School, CanonicalChild,
)

BATCH_SIZE = 500


class Command(BaseCommand):
    """
    Backfill resolved FK fields on 2026 session tables.

    Looks up Youth/School/CanonicalChild by UID string fields and sets the
    corresponding FK. Useful after initial sync or when canonical tables are
    updated independently of session syncs.
    """
    help = "Resolve FK fields on 2026 session tables from UID strings"

    def handle(self, *args, **options):
        youth_by_uid = {y.youth_uid: y for y in Youth.objects.filter(youth_uid__isnull=False)}
        school_by_uid = {s.school_uid: s for s in School.objects.filter(school_uid__isnull=False)}
        child_by_uid = {c.child_uid: c for c in CanonicalChild.objects.all()}

        self.stdout.write(f"Lookup sizes: youth={len(youth_by_uid)}, school={len(school_by_uid)}, child={len(child_by_uid)}")

        self.resolve_literacy(youth_by_uid, school_by_uid, child_by_uid)
        self.resolve_numeracy(youth_by_uid, school_by_uid)

    def resolve_literacy(self, youth_by_uid, school_by_uid, child_by_uid):
        self.stdout.write("\n--- LiteracySession2026 ---")

        for fk_field, uid_field, lookup in [
            ('youth', 'youth_uid', youth_by_uid),
            ('school', 'school_uid', school_by_uid),
            ('child_1', 'child_uid_1', child_by_uid),
            ('child_2', 'child_uid_2', child_by_uid),
        ]:
            qs = LiteracySession2026.objects.filter(
                **{f'{fk_field}__isnull': True, f'{uid_field}__isnull': False}
            ).exclude(**{uid_field: ''})

            to_update = []
            orphaned = 0
            for session in qs.iterator():
                uid_val = getattr(session, uid_field)
                resolved = lookup.get(uid_val)
                if resolved:
                    setattr(session, fk_field, resolved)
                    to_update.append(session)
                else:
                    orphaned += 1

                if len(to_update) >= BATCH_SIZE:
                    LiteracySession2026.objects.bulk_update(to_update, [fk_field], batch_size=BATCH_SIZE)
                    to_update = []

            if to_update:
                LiteracySession2026.objects.bulk_update(to_update, [fk_field], batch_size=BATCH_SIZE)

            resolved_count = qs.count()  # re-count after update (should be 0 if all resolved)
            total_resolved = LiteracySession2026.objects.filter(**{f'{fk_field}__isnull': False}).count()
            self.stdout.write(f"  {fk_field}: resolved={total_resolved}, orphaned={orphaned}")

    def resolve_numeracy(self, youth_by_uid, school_by_uid):
        self.stdout.write("\n--- NumeracySession2026 ---")

        for fk_field, uid_field, lookup in [
            ('youth', 'youth_uid', youth_by_uid),
            ('school', 'school_uid', school_by_uid),
        ]:
            qs = NumeracySession2026.objects.filter(
                **{f'{fk_field}__isnull': True, f'{uid_field}__isnull': False}
            ).exclude(**{uid_field: ''})

            to_update = []
            orphaned = 0
            for session in qs.iterator():
                uid_val = getattr(session, uid_field)
                resolved = lookup.get(uid_val)
                if resolved:
                    setattr(session, fk_field, resolved)
                    to_update.append(session)
                else:
                    orphaned += 1

                if len(to_update) >= BATCH_SIZE:
                    NumeracySession2026.objects.bulk_update(to_update, [fk_field], batch_size=BATCH_SIZE)
                    to_update = []

            if to_update:
                NumeracySession2026.objects.bulk_update(to_update, [fk_field], batch_size=BATCH_SIZE)

            total_resolved = NumeracySession2026.objects.filter(**{f'{fk_field}__isnull': False}).count()
            self.stdout.write(f"  {fk_field}: resolved={total_resolved}, orphaned={orphaned}")
