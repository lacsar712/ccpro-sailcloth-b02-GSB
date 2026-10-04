from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException

from .models import ClothRoll, DipRun, Loft, LoftDipCap
from .rules import (
    can_mark_roll_cured,
    dip_cap_block_reason,
    dips_used_today,
    lock_dip_cap,
)


class DailyDipCapExceeded(APIException):
    """当日该帆布间新登记浸渍条数到顶。"""

    status_code = 400
    default_code = "daily_dip_cap_exceeded"


class LoftSerializer(serializers.ModelSerializer):
    rollCount = serializers.SerializerMethodField()

    class Meta:
        model = Loft
        fields = ("id", "name", "location", "notes", "rollCount", "created_at")
        read_only_fields = ("id", "rollCount", "created_at")

    def get_rollCount(self, obj):
        if hasattr(obj, "roll_count"):
            return obj.roll_count
        return obj.rolls.count()


class ClothRollSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    rollCode = serializers.CharField(source="roll_code")
    fabricWeightGsm = serializers.IntegerField(source="fabric_weight_gsm", required=False)
    loftName = serializers.CharField(source="loft.name", read_only=True)

    class Meta:
        model = ClothRoll
        fields = (
            "id",
            "loftId",
            "loftName",
            "rollCode",
            "status",
            "fabricWeightGsm",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "created_at", "updated_at")

    def validate(self, attrs):
        loft = attrs.get("loft") or getattr(self.instance, "loft", None)
        roll_code = attrs.get("roll_code") or getattr(self.instance, "roll_code", None)
        if loft and roll_code:
            qs = ClothRoll.objects.filter(loft=loft, roll_code=roll_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"rollCode": "同一帆布间卷号必须唯一"})

        new_status = attrs.get("status")
        if new_status == ClothRoll.STATUS_CURED:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为已固化"}
                )
            # 合并未提交字段到临时视角：用当前实例校验
            ok, msg = can_mark_roll_cured(roll)
            if not ok:
                raise serializers.ValidationError({"status": msg})
        return attrs


class DipRunSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    startedAt = serializers.DateTimeField(source="started_at")
    resinPct = serializers.DecimalField(source="resin_pct", max_digits=5, decimal_places=2)
    cureHours = serializers.DecimalField(
        source="cure_hours",
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)

    class Meta:
        model = DipRun
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "startedAt",
            "resinPct",
            "cureHours",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "rollCode", "loftName", "created_at")

    def create(self, validated_data):
        roll = validated_data["roll"]
        loft = roll.loft
        # 行锁 + 事务：计数、校验、写入串行化，两名浸胶工并发登记也不会超登
        with transaction.atomic():
            cap = lock_dip_cap(loft)
            used = dips_used_today(loft)
            reason = dip_cap_block_reason(loft, cap, used)
            if reason:
                raise DailyDipCapExceeded(detail=reason)
            return super().create(validated_data)


class LoftDipCapSerializer(serializers.ModelSerializer):
    loftId = serializers.IntegerField(source="loft_id", read_only=True)
    loftName = serializers.CharField(source="loft.name", read_only=True)
    dailyCap = serializers.IntegerField(source="daily_cap", min_value=1, max_value=100000)
    usedToday = serializers.SerializerMethodField()
    remainingToday = serializers.SerializerMethodField()

    class Meta:
        model = LoftDipCap
        fields = (
            "id",
            "loftId",
            "loftName",
            "enabled",
            "dailyCap",
            "usedToday",
            "remainingToday",
        )
        read_only_fields = ("id", "loftId", "loftName", "usedToday", "remainingToday")

    def get_usedToday(self, obj):
        return dips_used_today(obj.loft)

    def get_remainingToday(self, obj):
        if not obj.enabled:
            return None
        return max(obj.daily_cap - dips_used_today(obj.loft), 0)
