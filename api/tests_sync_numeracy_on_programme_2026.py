from django.test import TestCase

from api.management.commands.sync_airtable_numeracy_on_programme_2026 import Command
from api.models import CanonicalChild, NumeracyOnTheProgramme2026


def roster_record(rid, uid="CH-1", **fields):
    values = {
        "Child UID": uid,
        "Programme Belonging": ["Numeracy Child"],
        "2026 On The Programme": "Yes",
        "Grade": "PreR",
        "School (from Sessions)": ["A School"],
        "Mentor (from Sessions)": ["A Mentor"],
        "Numeracy Coach Name (from Sessions)": ["A Coach"],
        "Total Sessions": 12,
        "Session School Count": 1,
        "Sessions": ["recSession"],
    }
    values.update(fields)
    return {"id": rid, "fields": values}


class RosterSyncTests(TestCase):
    def setUp(self):
        self.child = CanonicalChild.objects.create(
            source_airtable_id="recChild", child_uid="CH-1", mcode=1, full_name="Child One"
        )

    def test_maps_live_roster_fields_and_resolves_child(self):
        cmd = Command()
        row = cmd.extract_row(roster_record("recR"))
        self.assertEqual(row["numeracy_coach"], "A Coach")
        stats = cmd.bulk_upsert([roster_record("recR")], {"CH-1": self.child.id})
        saved = NumeracyOnTheProgramme2026.objects.get()
        self.assertEqual(stats["created"], 1)
        self.assertEqual(saved.child_id, self.child.id)

    def test_recreated_source_id_is_adopted_by_uid(self):
        NumeracyOnTheProgramme2026.objects.create(source_airtable_id="recOld", child_uid="CH-1")
        stats = Command().bulk_upsert([roster_record("recNew")], {"CH-1": self.child.id})
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(NumeracyOnTheProgramme2026.objects.get().source_airtable_id, "recNew")

    def test_duplicate_uid_pull_fails_before_writes(self):
        with self.assertRaisesMessage(ValueError, "duplicate child_uid"):
            Command().bulk_upsert(
                [roster_record("recA"), roster_record("recB")], {"CH-1": self.child.id}
            )
        self.assertEqual(NumeracyOnTheProgramme2026.objects.count(), 0)

    def test_blank_uid_is_rejected_and_reported(self):
        report = Command().qa_report([roster_record("recA", uid="")], {})
        self.assertEqual(report["blank_child_uids"], 1)

