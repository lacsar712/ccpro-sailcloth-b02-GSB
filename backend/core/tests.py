"""日条数封顶全链路测试。

覆盖验收点：
- 到顶后再登失败并给出中文原因
- 专页「今日已用」= 当天该间新插入的浸渍条数（按写入日计）
- 改卷态、标已固化不吃封顶
- 专页可改数字与启停；停用后可再登；调低后不可超登
- 两名浸胶工并发登记：到顶后两笔都被挡；未满时合计不超封顶
"""

import threading
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import ClothRoll, DipRun, Loft, LoftDipCap
from .rules import dips_used_today

User = get_user_model()


def make_loft(name="北岸帆布间"):
    return Loft.objects.create(name=name, location="港区二号库")


def make_roll(loft, code="R-01", status=ClothRoll.STATUS_RAW):
    return ClothRoll.objects.create(loft=loft, roll_code=code, status=status)


def dip_payload(roll, **over):
    payload = {
        "rollId": roll.id,
        "startedAt": timezone.now().isoformat(),
        "resinPct": "28.00",
        "cureHours": None,
        "notes": "",
    }
    payload.update(over)
    return payload


class DailyDipCapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="worker", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.loft = make_loft()
        self.roll = make_roll(self.loft)
        self.cap, _ = LoftDipCap.objects.get_or_create(loft=self.loft)
        self.cap.daily_cap = 2
        self.cap.enabled = True
        self.cap.save()

    def post_dip(self, roll=None, **over):
        return self.client.post(
            "/api/dips/", dip_payload(roll or self.roll, **over), format="json"
        )

    def test_cap_blocks_with_chinese_reason(self):
        self.assertEqual(self.post_dip().status_code, 201)
        self.assertEqual(self.post_dip().status_code, 201)
        resp = self.post_dip()
        self.assertEqual(resp.status_code, 400)
        detail = resp.data["detail"]
        self.assertIsInstance(detail, str)
        self.assertIn("封顶", detail)
        self.assertIn("2", detail)
        # 界面喊已满，库里不能多出一条
        self.assertEqual(DipRun.objects.filter(roll__loft=self.loft).count(), 2)

    def test_used_today_counts_insertions_not_started_at(self):
        yesterday = timezone.now() - timedelta(days=1)
        # startedAt 填昨天，仍按写入日计入今日
        self.assertEqual(self.post_dip(startedAt=yesterday.isoformat()).status_code, 201)
        self.assertEqual(dips_used_today(self.loft), 1)
        # 把写入时间拨回昨天后，不再计入今日
        DipRun.objects.all().update(created_at=yesterday)
        self.assertEqual(dips_used_today(self.loft), 0)

    def test_status_change_and_cured_not_capped(self):
        self.assertEqual(self.post_dip().status_code, 201)
        self.assertEqual(self.post_dip(cureHours="14.0").status_code, 201)
        self.assertEqual(self.post_dip().status_code, 400)  # 确认已到顶
        # 改卷态不吃封顶
        resp = self.client.patch(
            f"/api/rolls/{self.roll.id}/", {"status": "dipping"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        # 标已固化也不吃封顶（最近一条固化 14h ≥ 12h）
        resp = self.client.patch(
            f"/api/rolls/{self.roll.id}/", {"status": "cured"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)

    def test_disable_allows_registration(self):
        self.post_dip()
        self.post_dip()
        self.assertEqual(self.post_dip().status_code, 400)
        self.cap.enabled = False
        self.cap.save()
        self.assertEqual(self.post_dip().status_code, 201)
        self.assertEqual(DipRun.objects.filter(roll__loft=self.loft).count(), 3)

    def test_caps_api_used_matches_inserts(self):
        self.post_dip()
        resp = self.client.get("/api/caps/")
        self.assertEqual(resp.status_code, 200)
        row = [r for r in resp.data["results"] if r["loftId"] == self.loft.id][0]
        self.assertEqual(row["usedToday"], 1)
        self.assertEqual(row["dailyCap"], 2)
        self.assertEqual(row["remainingToday"], 1)
        self.assertTrue(row["enabled"])

    def test_caps_page_change_blocks_panel_overbooking(self):
        self.post_dip()
        self.post_dip()
        row = [r for r in self.client.get("/api/caps/").data["results"]][0]
        # 专页把封顶调低到已用条数以下 → 面板不可再超登
        resp = self.client.patch(f"/api/caps/{row['id']}/", {"dailyCap": 1}, format="json")
        self.assertEqual(resp.status_code, 200)
        resp = self.post_dip()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("封顶", resp.data["detail"])
        self.assertEqual(DipRun.objects.count(), 2)

    def test_caps_page_toggle_via_api(self):
        row = self.client.get("/api/caps/").data["results"][0]
        resp = self.client.patch(
            f"/api/caps/{row['id']}/", {"enabled": False}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["enabled"])
        self.assertIsNone(resp.data["remainingToday"])


class ConcurrentDipCapTests(TransactionTestCase):
    """两名浸胶工交叉登记：行锁保证不超登、到顶后两笔都被挡。"""

    def setUp(self):
        self.users = [
            User.objects.create_user(username=f"w{i}", password="x") for i in (1, 2)
        ]
        self.loft = make_loft()
        self.roll = make_roll(self.loft)
        LoftDipCap.objects.create(loft=self.loft, daily_cap=1, enabled=True)

    def _post_dip(self, username, results):
        try:
            client = APIClient()
            client.force_authenticate(User.objects.get(username=username))
            resp = client.post("/api/dips/", dip_payload(self.roll), format="json")
            results.append(resp.status_code)
        finally:
            connections.close_all()

    def _cross_post(self):
        results = []
        threads = [
            threading.Thread(target=self._post_dip, args=(u.username, results))
            for u in self.users
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return sorted(results)

    def test_two_workers_cannot_exceed_cap(self):
        self.assertEqual(self._cross_post(), [201, 400])
        self.assertEqual(DipRun.objects.count(), 1)

    def test_full_cap_blocks_both_workers(self):
        # 先登满（封顶 1 条）
        client = APIClient()
        client.force_authenticate(self.users[0])
        self.assertEqual(
            client.post("/api/dips/", dip_payload(self.roll), format="json").status_code,
            201,
        )
        # 到顶后两名浸胶工交叉再各登一条，两笔都要被挡住
        self.assertEqual(self._cross_post(), [400, 400])
        self.assertEqual(DipRun.objects.count(), 1)
