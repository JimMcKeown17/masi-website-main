"""Client for the Zazi iZandi backend.

Zazi iZandi data lives in a separate Django+Postgres service (Teampact-fed). The
Masi backend calls its existing API server-side with the shared-secret
`X-Internal-Auth` header and normalises the result into the WIG measure shape, so
the frontend only ever talks to the Masi backend. See
frontend `documentation/data-architecture.md`.
"""
import os

import requests

# Zazi WIG segments: (programme key, Zazi cohort, measure-key prefix). One cached
# snapshot row per cohort feeds the Primary and ECD tabs of the WIG board.
ZAZI_SEGMENTS = (
    ('zazi_izandi', 'primary', 'zazi'),
    ('zazi_izandi_ecd', 'ecd', 'zazi_ecd'),
)


def fetch_zazi_programme_overview(cohort=None, timeout=30):
    """GET the Zazi backend's pre-computed programme overview (KPIs + targets).

    `cohort` ('primary' | 'ecd') segments the overview by school type; omitted or
    'all' returns the combined cohort. The Zazi view takes ~10s to compute, so
    this runs out-of-band (via the refresh_zazi_overview cron) rather than on a
    user's board load. The timeout is generous because nothing user-facing waits.
    """
    base = os.environ.get('ZAZI_API_BASE_URL', '').rstrip('/')
    secret = os.environ.get('ZAZI_INTERNAL_API_SECRET', '')
    params = {'cohort': cohort} if cohort and cohort != 'all' else {}
    resp = requests.get(
        f'{base}/api/programme-overview/',
        headers={'X-Internal-Auth': secret},
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_zazi_snapshot(cohort='all', timeout=30):
    """Fetch the Zazi overview for a cohort and store it as that cohort's row.

    One snapshot row per cohort ('primary', 'ecd'). On failure the previous
    payload is preserved (so a transient Zazi outage doesn't blank the tile) and
    `ok` is set False. Returns the snapshot row.
    """
    from django.utils import timezone
    from .models import ZaziOverviewSnapshot

    snap, _ = ZaziOverviewSnapshot.objects.get_or_create(cohort=cohort)
    try:
        overview = fetch_zazi_programme_overview(cohort=cohort, timeout=timeout)
    except Exception as exc:  # keep last-good payload, record the error
        snap.ok = False
        snap.error_message = str(exc)
        snap.save()
        return snap

    snap.payload = overview
    snap.fetched_at = timezone.now()
    snap.ok = True
    snap.error_message = ''
    snap.save()
    return snap


def build_zazi_measures(overview, prefix='zazi'):
    """Map the Zazi programme-overview JSON into WIG measures.

    Zazi already computes these against its own `programme_targets`, so we pass
    through value + target rather than re-aggregating. `prefix` namespaces the
    keys so the Primary ('zazi') and ECD ('zazi_ecd') segments coexist in one map.
    """
    kpis = overview.get('kpis', {})
    targets = overview.get('targets', {})

    def measure(value, target, note):
        return {'value': value, 'target': target, 'calculation_note': note}

    return {
        'source': 'zazi_backend',
        'generated_at': overview.get('generated_at'),
        'measures': {
            f'{prefix}.pct_eas_on_track': measure(
                kpis.get('pct_eas_on_track'), targets.get('on_track_pct'),
                '% of EAs meeting the dosage target'),
            f'{prefix}.sessions_per_day': measure(
                kpis.get('avg_sessions_per_day_worked'), targets.get('dosage'),
                'avg sessions per day worked'),
            f'{prefix}.weighted_dosage': measure(
                kpis.get('weighted_dosage'), targets.get('dosage'),
                'weighted dosage across groups'),
        },
    }
