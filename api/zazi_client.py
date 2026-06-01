"""Client for the Zazi iZandi backend.

Zazi iZandi data lives in a separate Django+Postgres service (Teampact-fed). The
Masi backend calls its existing API server-side with the shared-secret
`X-Internal-Auth` header and normalises the result into the WIG measure shape, so
the frontend only ever talks to the Masi backend. See
frontend `documentation/data-architecture.md`.
"""
import os

import requests


def fetch_zazi_programme_overview(timeout=10):
    """GET the Zazi backend's pre-computed programme overview (KPIs + targets)."""
    base = os.environ.get('ZAZI_API_BASE_URL', '').rstrip('/')
    secret = os.environ.get('ZAZI_INTERNAL_API_SECRET', '')
    resp = requests.get(
        f'{base}/api/programme-overview/',
        headers={'X-Internal-Auth': secret},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def build_zazi_measures(overview):
    """Map the Zazi programme-overview JSON into WIG measures.

    Zazi already computes these against its own `programme_targets`, so we pass
    through value + target rather than re-aggregating.
    """
    kpis = overview.get('kpis', {})
    targets = overview.get('targets', {})

    def measure(value, target, note):
        return {'value': value, 'target': target, 'calculation_note': note}

    return {
        'source': 'zazi_backend',
        'generated_at': overview.get('generated_at'),
        'measures': {
            'zazi.pct_eas_on_track': measure(
                kpis.get('pct_eas_on_track'), targets.get('on_track_pct'),
                '% of EAs meeting the dosage target'),
            'zazi.sessions_per_day': measure(
                kpis.get('avg_sessions_per_day_worked'), targets.get('dosage'),
                'avg sessions per day worked'),
            'zazi.weighted_dosage': measure(
                kpis.get('weighted_dosage'), targets.get('dosage'),
                'weighted dosage across groups'),
        },
    }
