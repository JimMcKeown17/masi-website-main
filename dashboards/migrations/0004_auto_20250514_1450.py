from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('dashboards', '0003_alter_school_type'),  # Update this with your actual latest migration
    ]

    operations = [
        migrations.DeleteModel(
            name='School',
        ),
        migrations.DeleteModel(
            name='MentorVisit',
        ),
    ]