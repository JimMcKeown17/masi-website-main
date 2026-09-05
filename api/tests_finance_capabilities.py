"""Finance capability evaluation and API contracts."""

from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from api.permissions import FINANCE_PERMISSION_CAPABILITIES


def make_user(username: str, role: str) -> User:
    user = User.objects.create_user(username=username, password="x")
    user.profile.role = role
    user.profile.save()
    return user


class MeFinanceCapabilitiesTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_admin_receives_finance_read_without_a_django_permission_grant(self):
        user = make_user("finance_admin", "ADMIN")
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capabilities"], ["finance.publish", "finance.read"])

    def test_non_admin_superuser_receives_no_finance_capability(self):
        user = make_user("django_superuser", "STAFF")
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capabilities"], [])

    def test_finance_managers_group_member_receives_finance_read(self):
        user = make_user("finance_manager", "STAFF")
        user.groups.add(Group.objects.get(name="Finance Managers"))
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capabilities"], ["finance.read"])

    def test_direct_finance_permission_grant_is_evaluated_by_the_same_table(self):
        user = make_user("direct_finance_reader", "VIEWER")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="api",
                content_type__model="financesnapshot",
                codename="read_finance",
            )
        )
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capabilities"], ["finance.read"])

    def test_project_manager_and_staff_have_empty_capability_lists_without_grants(self):
        for role in ("PROJECT MANAGER", "STAFF"):
            with self.subTest(role=role):
                user = make_user(f"plain_{role.replace(' ', '_').lower()}", role)
                self.client.force_authenticate(user=user)

                response = self.client.get("/api/me/")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["capabilities"], [])

    def test_missing_profile_fails_closed_to_an_empty_capability_list(self):
        user = User.objects.create_user(username="missing_profile", password="x")
        user.profile.delete()
        self.client.force_authenticate(user=User.objects.get(pk=user.pk))

        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capabilities"], [])

    def test_inactive_admin_has_no_finance_capabilities(self):
        user = make_user("inactive_admin", "ADMIN")
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.client.force_authenticate(user=user)

        response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capabilities"], [])

    def test_one_evaluator_table_row_adds_a_future_capability_and_output_stays_sorted(self):
        user = make_user("future_finance_reader", "STAFF")
        permission = Permission.objects.create(
            name="Can read finance coverage",
            codename="read_finance_coverage",
            content_type=ContentType.objects.get_for_model(User),
        )
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="api",
                content_type__model="financesnapshot",
                codename="read_finance",
            ),
            permission,
        )
        self.client.force_authenticate(user=user)

        with patch.dict(
            FINANCE_PERMISSION_CAPABILITIES,
            {"auth.read_finance_coverage": "finance.coverage.read"},
        ):
            response = self.client.get("/api/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["capabilities"],
            ["finance.coverage.read", "finance.read"],
        )


class FinanceManagerMigrationContractTests(TestCase):
    def test_fresh_database_has_an_empty_finance_managers_group_with_the_read_grant(self):
        group = Group.objects.get(name="Finance Managers")

        self.assertEqual(
            set(group.permissions.values_list("content_type__app_label", "codename")),
            {("api", "read_finance")},
        )
        self.assertFalse(group.user_set.exists())
        self.assertTrue(Permission.objects.filter(content_type__model="financerun", codename="publish_finance").exists())
        self.assertFalse(Group.objects.filter(permissions__codename="publish_finance").exists())

    def test_forward_migration_preserves_existing_members_and_unrelated_grants(self):
        group = Group.objects.get(name="Finance Managers")
        member = make_user("existing_finance_member", "STAFF")
        group.user_set.add(member)
        unrelated = Permission.objects.get(
            content_type__app_label="auth",
            codename="view_group",
        )
        group.permissions.add(unrelated)

        migration = import_module("api.migrations.0050_finance_read_capability")
        migration.grant_finance_read_to_group(apps, schema_editor=None)

        self.assertTrue(group.user_set.filter(pk=member.pk).exists())
        self.assertTrue(group.permissions.filter(pk=unrelated.pk).exists())
        self.assertTrue(group.permissions.filter(codename="read_finance").exists())


class FinancePublishMappingTests(TestCase):
    def test_exact_released_mapping(self):
        self.assertEqual(FINANCE_PERMISSION_CAPABILITIES, {
            'api.read_finance':'finance.read', 'api.publish_finance':'finance.publish'})
