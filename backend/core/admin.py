from django.contrib import admin

from .models import ClothRoll, DailyDipCap, DipRun, Loft


@admin.register(DailyDipCap)
class DailyDipCapAdmin(admin.ModelAdmin):
    list_display = ("loft", "enabled", "limit", "updated_at")
    list_filter = ("enabled",)


admin.site.register(Loft)
admin.site.register(ClothRoll)
admin.site.register(DipRun)
