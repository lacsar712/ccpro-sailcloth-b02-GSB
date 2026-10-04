from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, DipRun, Loft, LoftDipCap
from .rules import DEFAULT_DAILY_DIP_CAP
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftDipCapSerializer,
    LoftSerializer,
)


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer

    def perform_create(self, serializer):
        loft = serializer.save()
        LoftDipCap.objects.get_or_create(loft=loft)


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


class LoftDipCapViewSet(viewsets.ModelViewSet):
    """日条数封顶专页：列出各帆布间封顶配置与当日已用，支持改数字与启停。"""

    serializer_class = LoftDipCapSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        self._ensure_cap_rows()
        return LoftDipCap.objects.select_related("loft").order_by("loft_id")

    @staticmethod
    def _ensure_cap_rows():
        have = set(LoftDipCap.objects.values_list("loft_id", flat=True))
        missing = [
            LoftDipCap(loft_id=loft.id, daily_cap=DEFAULT_DAILY_DIP_CAP)
            for loft in Loft.objects.exclude(id__in=have)
        ]
        if missing:
            LoftDipCap.objects.bulk_create(missing, ignore_conflicts=True)


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
