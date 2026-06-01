"""Custom DRF permissions."""
from rest_framework.permissions import BasePermission

WIG_ALLOWED_ROLES = {'ADMIN', 'PROJECT MANAGER'}


class IsAdminOrProjectManager(BasePermission):
    """Authorization (not just authentication): the user must be authenticated
    AND have a UserProfile role of ADMIN or PROJECT MANAGER. Missing profile or
    any other role is denied. Applies equally to Clerk and Session auth users.
    """

    message = 'WIG dashboard access is limited to admins and project managers.'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        profile = getattr(user, 'profile', None)
        return bool(profile and profile.role in WIG_ALLOWED_ROLES)
