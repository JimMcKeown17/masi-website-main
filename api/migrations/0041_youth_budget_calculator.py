import decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0040_numeracy_assessment_pipeline_2026'),
    ]

    operations = [
        migrations.AddField(
            model_name='youth',
            name='subsidy_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='youth',
            name='subsidy_funder',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='youth',
            name='subsidy_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='youth',
            name='subsidy_status',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.CreateModel(
            name='BudgetScenario',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('year', models.IntegerField(unique=True)),
                (
                    'wage_rate',
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal('32.01'),
                        max_digits=6,
                    ),
                ),
                (
                    'subsidy_contribution',
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal('1600'),
                        max_digits=8,
                    ),
                ),
                ('hours_matrix', models.JSONField(default=dict)),
                ('nys_conversion_count', models.IntegerField(default=200)),
                (
                    'nys_conversion_start_month',
                    models.PositiveSmallIntegerField(default=8),
                ),
                ('vacancy_start_month', models.PositiveSmallIntegerField(default=8)),
                (
                    'holiday_pay',
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal('0'),
                        max_digits=12,
                    ),
                ),
                (
                    'mentor_reserve',
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal('0'),
                        max_digits=12,
                    ),
                ),
                ('updated_by', models.CharField(blank=True, max_length=200)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='FundingPot',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('year', models.IntegerField()),
                ('funder_name', models.CharField(max_length=200)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('as_of', models.DateField()),
                ('note', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'schools',
                    models.ManyToManyField(
                        blank=True,
                        related_name='funding_pots',
                        to='api.school',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='MonthlyYouthExpenditure',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('year', models.IntegerField()),
                ('month', models.PositiveSmallIntegerField()),
                (
                    'core_amount',
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal('0'),
                        max_digits=12,
                    ),
                ),
                (
                    'mentor_amount',
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal('0'),
                        max_digits=12,
                    ),
                ),
                (
                    'rural_amount',
                    models.DecimalField(
                        decimal_places=2,
                        default=decimal.Decimal('0'),
                        max_digits=12,
                    ),
                ),
                ('note', models.TextField(blank=True)),
            ],
            options={
                'unique_together': {('year', 'month')},
            },
        ),
    ]
