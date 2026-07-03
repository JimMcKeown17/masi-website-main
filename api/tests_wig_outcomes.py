"""Tests for the literacy WIG outcome measures (api/wig_outcomes.py)."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from api.models import AirtableSyncLog, LiteracyAssessment2026, OnTheProgramme2026
from api.wig_outcomes import REQUIRED_SYNCS, check_sources

_seq = {"n": 0}


def make_logs(hours_ago=1, success=True, details=None, only=None):
    """Create a sync log per required sync type (or `only` a subset)."""
    for sync_type in (only or REQUIRED_SYNCS):
        AirtableSyncLog.objects.create(
            sync_type=sync_type, success=success,
            completed_at=timezone.now() - timedelta(hours=hours_ago),
            details=details,
        )


def roster(uid, grade="Grade 1", on_programme=True, active=True):
    _seq["n"] += 1
    return OnTheProgramme2026.objects.create(
        source_airtable_id=f"rec-r{_seq['n']}", child_uid=uid,
        on_the_programme=on_programme, grade=grade, is_active=active)


def assess(uid, term="Jun", read_words=None, letter_sounds=None, grade=None,
           duplicate_status="Single", year=2026, active=True):
    _seq["n"] += 1
    return LiteracyAssessment2026.objects.create(
        source_airtable_id=f"rec-a{_seq['n']}", child_uid=uid, year=year, term=term,
        grade=grade, read_words=read_words, letter_sounds=letter_sounds,
        duplicate_status=duplicate_status, is_active=active)


class CheckSourcesTests(TestCase):
    """Fail-closed source gate: exporter's _assert_synced rules + 48h dead-cron age."""

    def test_no_logs_fails(self):
        ok, note = check_sources(timezone.now())
        self.assertFalse(ok)
        self.assertIn("literacy_assessments_2026", note)

    def test_failed_latest_sync_fails(self):
        make_logs(success=False)
        ok, note = check_sources(timezone.now())
        self.assertFalse(ok)
        self.assertIn("failed", note)

    def test_newer_failed_sync_not_masked_by_older_success(self):
        make_logs(hours_ago=5, success=True)
        make_logs(hours_ago=1, success=False, only=("literacy_assessments_2026",))
        ok, _ = check_sources(timezone.now())
        self.assertFalse(ok)

    def test_flagged_details_fail(self):
        make_logs(details={"retire_skipped": 2})
        ok, note = check_sources(timezone.now())
        self.assertFalse(ok)
        self.assertIn("flagged", note)

    def test_stale_sync_fails(self):
        make_logs(hours_ago=72)
        ok, note = check_sources(timezone.now())
        self.assertFalse(ok)
        self.assertIn("48", note)

    def test_one_fresh_one_stale_fails(self):
        make_logs(hours_ago=1, only=("literacy_assessments_2026",))
        make_logs(hours_ago=72, only=("on_the_programme_2026",))
        ok, _ = check_sources(timezone.now())
        self.assertFalse(ok)

    def test_healthy_logs_pass(self):
        make_logs(hours_ago=1)
        ok, note = check_sources(timezone.now())
        self.assertTrue(ok)
        self.assertIsNone(note)
