import django.db.models.deletion
from django.db import migrations, models


def create_caps_for_existing_lofts(apps, schema_editor):
    Loft = apps.get_model("core", "Loft")
    LoftDipCap = apps.get_model("core", "LoftDipCap")
    for loft in Loft.objects.all():
        LoftDipCap.objects.get_or_create(loft=loft)


def drop_caps(apps, schema_editor):
    LoftDipCap = apps.get_model("core", "LoftDipCap")
    LoftDipCap.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoftDipCap",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("daily_cap", models.PositiveIntegerField(default=20)),
                ("enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "loft",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dip_cap",
                        to="core.loft",
                    ),
                ),
            ],
            options={"ordering": ["loft_id"]},
        ),
        migrations.RunPython(create_caps_for_existing_lofts, drop_caps),
    ]
