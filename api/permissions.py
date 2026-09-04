"""Custom DRF permissions."""
import hmac

from django.conf import settings
from django.contrib.auth.models import Permission
from django.db.models import Q
from rest_framework.permissions import BasePermission

WIG_ALLOWED_ROLES = {'ADMIN', 'PROJECT MANAGER'}

# Application code speaks capabilities; this is the only translation from
# Django permission names. Future finance read capabilities are added here.
FINANCE_PERMISSION_CAPABILITIES = {
    "api.read_finance": "finance.read",
}
FINANCE_CAPABILITY_VOCABULARY = frozenset({
    *FINANCE_PERMISSION_CAPABILITIES.values(),
    "finance.publish",  # Reserved for WP2; no Django permission exists yet.
})


def finance_capabilities_for(user):
    """Return sorted finance capabilities from explicit application grants.

    Django's ``has_perm`` gives superusers every permission, which is not the
    finance policy. Query direct/group grants explicitly and keep ADMIN as the
    sole role-based override.
    """
    if not user or not user.is_authenticated or not user.is_active:
        return []
    profile = getattr(user, "profile", None)
    if profile is None:
        return []
    if profile.role == "ADMIN":
        return sorted(FINANCE_PERMISSION_CAPABILITIES.values())

    permission_parts = [permission_name.split(".", 1) for permission_name in FINANCE_PERMISSION_CAPABILITIES]
    app_labels = {app_label for app_label, _ in permission_parts}
    codenames = {codename for _, codename in permission_parts}
    granted = {
        f"{app_label}.{codename}"
        for app_label, codename in Permission.objects.filter(
            Q(user=user) | Q(group__user=user),
            content_type__app_label__in=app_labels,
            codename__in=codenames,
        ).values_list("content_type__app_label", "codename").distinct()
    }
    return sorted(
        capability
        for permission_name, capability in FINANCE_PERMISSION_CAPABILITIES.items()
        if permission_name in granted
    )


class IsAdminOrProjectManager(BasePermission):
    """Authorization (not just authentication): the user must be authenticated
    AND have a UserProfile role of ADMIN or PROJECT MANAGER. Missing profile or
    any other role is denied. Applies equally to Clerk and Session auth users.
    """

    message = 'Access is limited to admins and project managers.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        profile = getattr(user, 'profile', None)
        return bool(profile and profile.role in WIG_ALLOWED_ROLES)


class IsFinanceReader(BasePermission):
    """Require the explicit finance.read application capability."""

    message = 'Finance access is not granted for this account.'

    def has_permission(self, request, view):
        return "finance.read" in finance_capabilities_for(getattr(request, "user", None))


class IsInternalService(BasePermission):
    """Service-to-service auth (no user identity): a matching X-Internal-Auth
    shared secret. Used by the Zazi backend to pull the closure/absence export.
    Constant-time compared; an unset/empty server secret denies everyone.
    """

    message = 'Invalid or missing internal service credentials.'

    def has_permission(self, request, view):
        secret = getattr(settings, 'MASI_INTERNAL_API_SECRET', '') or ''
        provided = request.headers.get('X-Internal-Auth', '') or ''
        return bool(secret) and hmac.compare_digest(secret, provided)
