"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError
from django.utils import timezone

from .models import ClothRoll, DipRun, Loft, LoftDipCap

MIN_CURE_HOURS_FOR_CURED = Decimal("12")

# 帆布间当天允许新登记浸渍条数的默认封顶
DEFAULT_DAILY_DIP_CAP = 20


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


def dips_used_today(loft: Loft) -> int:
    """当天该帆布间新插入的浸渍条数（按记录写入日计，与右侧面板那次写入一致）。"""
    return DipRun.objects.filter(
        roll__loft=loft, created_at__date=timezone.localdate()
    ).count()


def lock_dip_cap(loft: Loft) -> LoftDipCap:
    """
    在当前事务内锁定并返回该帆布间的日封顶配置行（不存在则创建）。
    必须配合 transaction.atomic() 使用：行锁把「计数 + 校验 + 写入」串行化，
    两名浸胶工同时登记时后到者会看到前者的写入结果。
    """
    try:
        cap, _ = LoftDipCap.objects.select_for_update().get_or_create(
            loft=loft, defaults={"daily_cap": DEFAULT_DAILY_DIP_CAP}
        )
    except IntegrityError:
        # 并发首建：另一事务已写入配置行，重新锁定读取
        cap = LoftDipCap.objects.select_for_update().get(loft=loft)
    return cap


def dip_cap_block_reason(loft: Loft, cap: LoftDipCap, used: int) -> str | None:
    """返回 None 表示可继续登记；否则返回中文原因。"""
    if not cap.enabled:
        return None
    if used >= cap.daily_cap:
        return (
            f"今日「{loft.name}」新登记浸渍已达日条数封顶 {cap.daily_cap} 条"
            f"（已用 {used} 条），无法继续登记；"
            "请在「日条数封顶」页调高条数或暂停启用后再试"
        )
    return None
