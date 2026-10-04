import django.db.models.deletion
from django.db import migrations, models


def create_caps_for_existing_lofts(apps, schema_editor):
    Loft = apps.get_model("core", "Loft")
    DailyDipCap = apps.get_model("core", "DailyDipCap")
    DailyDipCap.objects.bulk_create(
        [DailyDipCap(loft_id=loft.pk, enabled=False, limit=10)
         for loft in Loft.objects.all()]
    )


def remove_caps(apps, schema_editor):
    DailyDipCap = apps.get_model("core", "DailyDipCap")
    DailyDipCap.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyDipCap",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("enabled", models.BooleanField(default=False)),
                ("limit", models.PositiveIntegerField(default=10)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "loft",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_dip_cap",
                        to="core.loft",
                    ),
                ),
            ],
            options={"ordering": ["loft_id"]},
        ),
        migrations.RunPython(
            create_caps_for_existing_lofts, reverse_code=remove_caps
        ),
    ]
