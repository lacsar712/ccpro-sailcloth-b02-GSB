"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from .models import ClothRoll, DipRun, Loft

MIN_CURE_HOURS_FOR_CURED = Decimal("12")


def latest_dip_run(roll: ClothRoll) -> DipRun | None:
    return roll.dip_runs.order_by("-started_at", "-id").first()


def can_mark_roll_cured(roll: ClothRoll) -> tuple[bool, str]:
    """
    布卷转为「已固化」(cured) 的前提：
    最近一条浸渍记录的固化时长已记录，且 >= 12 小时。
    """
    latest = latest_dip_run(roll)
    if latest is None:
        return False, "该布卷尚无浸渍记录，不能标记为已固化"
    if latest.cure_hours is None:
        return False, "最近浸渍记录尚未填写固化时长，不能标记为已固化"
    if latest.cure_hours < MIN_CURE_HOURS_FOR_CURED:
        return (
            False,
            f"最近浸渍固化时长 {latest.cure_hours} 小时低于 {MIN_CURE_HOURS_FOR_CURED} 小时，不能标记为已固化",
        )
    return True, ""


def count_dips_inserted_today(loft: Loft, today=None) -> int:
    """
    当天该帆布间「新插入的浸渍条数」。以 DipRun.created_at（写入时刻）为准，
    而不是 started_at（登记时手填的开工时刻），保证专页已用数字
    与右侧面板每次实际写入一一对应。
    """
    if today is None:
        today = timezone.localdate()
    return DipRun.objects.filter(
        roll__loft=loft, created_at__date=today
    ).aggregate(n=Count("id"))["n"] or 0


def check_daily_dip_cap(
    loft: Loft, used: int | None = None, cap: "DailyDipCap | None" = None
) -> tuple[bool, str, int]:
    """
    返回 (是否放行, 中文原因, 当天已用条数)。
    仅约束「新登记浸渍」；改卷态、标已固化不走这里。
    cap 可由调用方在事务里 select_for_update 锁定后传入，保证并发不超登。
    """
    if cap is None:
        cap = getattr(loft, "daily_dip_cap", None)
    if cap is None or not cap.enabled:
        return True, "", used if used is not None else count_dips_inserted_today(loft)
    if used is None:
        used = count_dips_inserted_today(loft)
    if used >= cap.limit:
        return (
            False,
            f"「{loft.name}」今日浸渍登记已达封顶 {cap.limit} 条（已用 {used} 条），"
            f"不能再登记新浸渍",
            used,
        )
    return True, "", used
