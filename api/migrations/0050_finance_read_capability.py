from django.db import migrations


GROUP_NAME = "Finance Managers"
PERMISSION_CODENAME = "read_finance"


def grant_finance_read_to_group(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    content_type, _ = ContentType.objects.get_or_create(
        app_label="api",
        model="financesnapshot",
    )
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename=PERMISSION_CODENAME,
        defaults={"name": "Can read the finance dashboard"},
    )
    group, _ = Group.objects.get_or_create(name=GROUP_NAME)
    group.permissions.add(permission)


def remove_finance_read_from_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    group = Group.objects.filter(name=GROUP_NAME).first()
    permission = Permission.objects.filter(
        content_type__app_label="api",
        codename=PERMISSION_CODENAME,
    ).first()
    if group is not None and permission is not None:
        # Preserve the group, its memberships, and any unrelated grants if a
        # production rollback happens after Jim has assigned members.
        group.permissions.remove(permission)


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0049_finance_snapshot"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="financesnapshot",
            options={
                "permissions": [("read_finance", "Can read the finance dashboard")],
                "verbose_name": "Finance Snapshot",
                "verbose_name_plural": "Finance Snapshots",
            },
        ),
        migrations.RunPython(
            grant_finance_read_to_group,
            remove_finance_read_from_group,
        ),
    ]
