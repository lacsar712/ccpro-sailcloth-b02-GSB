from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DailyDipCap, Loft


@receiver(post_save, sender=Loft)
def ensure_daily_dip_cap(sender, instance, created, **kwargs):
    if created:
        DailyDipCap.objects.get_or_create(loft=instance)
