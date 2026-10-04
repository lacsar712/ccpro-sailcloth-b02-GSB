from rest_framework import serializers

from .models import ClothRoll, DailyDipCap, DipRun, Loft
from .rules import can_mark_roll_cured, check_daily_dip_cap, count_dips_inserted_today


class DailyDipCapSerializer(serializers.ModelSerializer):
    loftName = serializers.CharField(source="loft.name", read_only=True)
    usedToday = serializers.SerializerMethodField()

    class Meta:
        model = DailyDipCap
        fields = ("id", "loft", "loftName", "enabled", "limit", "usedToday", "updated_at")
        read_only_fields = ("id", "loft", "loftName", "usedToday", "updated_at")
        extra_kwargs = {
            "limit": {"min_value": 0},
        }

    def get_usedToday(self, obj):
        return count_dips_inserted_today(obj.loft)


class LoftSerializer(serializers.ModelSerializer):
    rollCount = serializers.SerializerMethodField()
    capEnabled = serializers.BooleanField(source="daily_dip_cap.enabled", required=False)
    capLimit = serializers.IntegerField(
        source="daily_dip_cap.limit", required=False, min_value=0
    )
    capUsedToday = serializers.SerializerMethodField()

    class Meta:
        model = Loft
        fields = (
            "id",
            "name",
            "location",
            "notes",
            "rollCount",
            "capEnabled",
            "capLimit",
            "capUsedToday",
            "created_at",
        )
        read_only_fields = ("id", "rollCount", "capUsedToday", "created_at")

    def get_rollCount(self, obj):
        if hasattr(obj, "roll_count"):
            return obj.roll_count
        return obj.rolls.count()

    def get_capUsedToday(self, obj):
        cap = getattr(obj, "daily_dip_cap", None)
        if cap is None:
            return None
        return count_dips_inserted_today(obj)

    def _cap_payload(self, validated_data):
        return validated_data.pop("daily_dip_cap", None)

    def _apply_cap(self, instance, cap_data):
        if cap_data is None:
            return
        cap, _ = DailyDipCap.objects.get_or_create(loft=instance)
        changed = False
        if "enabled" in cap_data:
            cap.enabled = cap_data["enabled"]
            changed = True
        if "limit" in cap_data:
            cap.limit = cap_data["limit"]
            changed = True
        if changed:
            cap.save()

    def create(self, validated_data):
        cap_data = self._cap_payload(validated_data)
        loft = super().create(validated_data)
        # post_save 信号已建行；补上客户端可能提交的封顶设置
        self._apply_cap(loft, cap_data or {})
        return loft

    def update(self, instance, validated_data):
        cap_data = self._cap_payload(validated_data)
        super().update(instance, validated_data)
        if cap_data is not None:
            self._apply_cap(instance, cap_data)
        return instance


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
