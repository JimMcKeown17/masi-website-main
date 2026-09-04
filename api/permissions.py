"""Custom DRF permissions."""
import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission

WIG_ALLOWED_ROLES = {'ADMIN', 'PROJECT MANAGER'}


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
    """Finance dashboards are ADMIN-only until capability grants ship.

    The frontend guard is defence in depth; this class is the trust boundary.
    Missing profiles and every non-ADMIN role fail closed.
    """

    message = 'Finance dashboards are limited to admins.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        profile = getattr(user, 'profile', None)
        return bool(profile and profile.role == 'ADMIN')


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
