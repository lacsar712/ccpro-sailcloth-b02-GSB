from django.db import transaction
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DailyDipCap, DipRun, Loft
from .rules import check_daily_dip_cap, count_dips_inserted_today
from .serializers import (
    ClothRollSerializer,
    DailyDipCapSerializer,
    DipRunSerializer,
    LoftSerializer,
)


class LoftViewSet(viewsets.ModelViewSet):
    serializer_class = LoftSerializer
    queryset = (
        Loft.objects.annotate(roll_count=Count("rolls"))
        .select_related("daily_dip_cap")
        .all()
    )

    @action(detail=True, methods=["get", "patch"])
    def cap(self, request, pk=None):
        """读取/修改某帆布间当天浸渍条数封顶（数字与是否启用）。"""
        loft = self.get_object()
        cap, _ = DailyDipCap.objects.get_or_create(loft=loft)
        if request.method.lower() == "patch":
            serializer = DailyDipCapSerializer(
                cap, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            serializer = DailyDipCapSerializer(cap)
        return Response(serializer.data)


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft").all()
        loft_id = self.request.query_params.get("loftId")
        status = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        roll = serializer.validated_data["roll"]

        # 串行化同一帆布间的浸渍写入：锁 loft 行后再按「当天新插入条数」判顶。
        # 两名浸胶工并发各登一笔时，后到者会拿到锁后重算的计数并被挡下。
        with transaction.atomic():
            loft = Loft.objects.select_for_update().get(pk=roll.loft_id)
            cap, _ = DailyDipCap.objects.get_or_create(loft=loft)
            used = count_dips_inserted_today(loft)
            ok, msg, used = check_daily_dip_cap(loft, used=used, cap=cap)
            if not ok:
                raise PermissionDenied(msg)
            serializer.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
    }
    return Response(data)
