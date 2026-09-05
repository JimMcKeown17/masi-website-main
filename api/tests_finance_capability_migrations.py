from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class CapabilityMigrationTests(TransactionTestCase):
    migrate_from=('api','0050_finance_read_capability')
    migrate_to=('api','0051_finance_runs_foundation')

    def test_upgrade_copies_all_read_grants_no_publish_and_reverse_restores(self):
        executor=MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old=executor.loader.project_state([self.migrate_from]).apps
        Permission=old.get_model('auth','Permission'); Group=old.get_model('auth','Group'); User=old.get_model('auth','User')
        read=Permission.objects.get(codename='read_finance',content_type__model='financesnapshot')
        user=User.objects.create(username='migration_direct')
        group=Group.objects.create(name='migration_group')
        user.user_permissions.add(read); group.permissions.add(read); user.groups.add(group)
        unrelated=Permission.objects.get(codename='view_group',content_type__app_label='auth')
        group.permissions.add(unrelated)
        try:
            executor=MigrationExecutor(connection); executor.migrate([self.migrate_to])
            new=executor.loader.project_state([self.migrate_to]).apps
            P=new.get_model('auth','Permission'); G=new.get_model('auth','Group'); U=new.get_model('auth','User')
            copied=P.objects.get(codename='read_finance',content_type__model='financerun')
            publish=P.objects.get(codename='publish_finance',content_type__model='financerun')
            self.assertTrue(U.objects.get(pk=user.pk).user_permissions.filter(pk=copied.pk).exists())
            self.assertTrue(G.objects.get(pk=group.pk).permissions.filter(pk=copied.pk).exists())
            self.assertFalse(publish.user_set.exists()); self.assertFalse(publish.group_set.exists())
            self.assertTrue(U.objects.get(pk=user.pk).groups.filter(pk=group.pk).exists())
            self.assertTrue(G.objects.get(pk=group.pk).permissions.filter(pk=unrelated.pk).exists())
            U.objects.get(pk=user.pk).user_permissions.remove(read.pk)
            G.objects.get(pk=group.pk).permissions.remove(read.pk)
            executor=MigrationExecutor(connection); executor.migrate([self.migrate_from])
            self.assertTrue(User.objects.get(pk=user.pk).user_permissions.filter(pk=read.pk).exists())
            self.assertTrue(Group.objects.get(pk=group.pk).permissions.filter(pk=read.pk).exists())
            self.assertFalse(Permission.objects.filter(content_type__model='financerun',codename__in=['read_finance','publish_finance']).exists())
        finally:
            executor=MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())

    def test_fresh_install_permissions(self):
        from django.contrib.auth.models import Permission,Group
        self.assertTrue(Permission.objects.filter(codename='publish_finance',content_type__model='financerun').exists())
        self.assertFalse(Group.objects.filter(permissions__codename='publish_finance').exists())
        self.assertEqual(set(Group.objects.get(name='Finance Managers').permissions.filter(codename='read_finance').values_list('content_type__model',flat=True)),{'financesnapshot','financerun'})
