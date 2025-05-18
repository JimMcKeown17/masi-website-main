from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_alter_youth_field_lengths'),
    ]

    operations = [
        migrations.AlterField(
            model_name='youth',
            name='employment_status',
            field=models.CharField(choices=[('Active', 'Active'), ('Inactive', 'Inactive')], default='Active', max_length=100),
        ),
        migrations.AlterField(
            model_name='youth',
            name='account_type',
            field=models.CharField(blank=True, choices=[('Savings', 'Savings'), ('Current', 'Current'), ('Cheque', 'Cheque')], max_length=100, null=True),
        ),
    ] 