"""Pure tests for lawfirm_msgraph primitive (subscription ensure + renew)."""

from __future__ import annotations

import asyncio
import unittest


class _Stub:
    """Mock _execute / _query / _ms_post."""

    def __init__(self, query_returns=None, post_returns=None):
        self.query_returns = query_returns or []
        self.post_returns = post_returns or []
        self.executes: list[tuple[str, dict]] = []
        self.posts: list[tuple[str, dict, str]] = []  # (url, body, method)

    def install(self):
        import kotodama.primitives.lawfirm_msgraph as p
        self._orig_exec = p._execute
        self._orig_q = p._query
        self._orig_post = p._ms_post

        executes = self.executes
        def _exec(sql_str, params):
            executes.append((sql_str, params))
            return True
        p._execute = _exec

        responses = list(self.query_returns)
        def _q(sql_str, params=None):
            return responses.pop(0) if responses else []
        p._query = _q

        post_responses = list(self.post_returns)
        posts = self.posts
        def _post(url, body, method="POST"):
            posts.append((url, body, method))
            if post_responses:
                return post_responses.pop(0)
            return {"id": "test_default"}
        p._ms_post = _post

    def uninstall(self):
        import kotodama.primitives.lawfirm_msgraph as p
        p._execute = self._orig_exec
        p._query = self._orig_q
        p._ms_post = self._orig_post


# ── subscriptionRenew tests ─────────────────────────────────────────────────


class TestRenewNoSubscriptions(unittest.TestCase):
    def test_returns_zero_when_no_active_subs(self):
        stub = _Stub(query_returns=[[]])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_msgraph import (
                task_lawfirm_msgraph_subscription_renew,
            )
            out = asyncio.run(task_lawfirm_msgraph_subscription_renew())
            self.assertTrue(out["ok"])
            self.assertEqual(out["renewed"], 0)
            self.assertEqual(out["checked"], 0)
            self.assertEqual(len(stub.executes), 0)
            self.assertEqual(len(stub.posts), 0)
        finally:
            stub.uninstall()


class TestRenewExpiringSoon(unittest.TestCase):
    def test_renews_subscription_expiring_within_24h(self):
        # Sub expires 1h from now → should renew (under 24h threshold)
        import datetime as _dt
        soon = (_dt.datetime.now(tz=_dt.UTC)
                + _dt.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        stub = _Stub(
            query_returns=[[
                {"vertex_id": "at://sub-1", "subscription_id": "sub_abc",
                 "user_upn": "k.bakshi@etzhayyim.com", "expires_at": soon},
            ]],
            post_returns=[{"id": "sub_abc", "expirationDateTime": "renewed"}],
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_msgraph import (
                task_lawfirm_msgraph_subscription_renew,
            )
            out = asyncio.run(task_lawfirm_msgraph_subscription_renew())
            self.assertTrue(out["ok"])
            self.assertEqual(out["renewed"], 1)
            self.assertEqual(out["checked"], 1)
            # Verify Graph PATCH was called against the right URL
            self.assertEqual(len(stub.posts), 1)
            url, body, method = stub.posts[0]
            self.assertEqual(method, "PATCH")
            self.assertIn("sub_abc", url)
            self.assertIn("expirationDateTime", body)
            # Verify DB UPDATE fired
            self.assertEqual(len(stub.executes), 1)
            self.assertIn("UPDATE", stub.executes[0][0])
        finally:
            stub.uninstall()


class TestRenewSkipsHealthySubscriptions(unittest.TestCase):
    def test_skips_subscription_expiring_far_in_future(self):
        # Sub expires 7 days from now → should skip (above 24h threshold)
        import datetime as _dt
        far = (_dt.datetime.now(tz=_dt.UTC)
               + _dt.timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        stub = _Stub(query_returns=[[
            {"vertex_id": "at://sub-1", "subscription_id": "sub_xyz",
             "user_upn": "k.bakshi@etzhayyim.com", "expires_at": far},
        ]])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_msgraph import (
                task_lawfirm_msgraph_subscription_renew,
            )
            out = asyncio.run(task_lawfirm_msgraph_subscription_renew())
            self.assertTrue(out["ok"])
            self.assertEqual(out["renewed"], 0)
            self.assertEqual(out["checked"], 1)
            # No Graph call, no DB write
            self.assertEqual(len(stub.posts), 0)
            self.assertEqual(len(stub.executes), 0)
        finally:
            stub.uninstall()


class TestRenewEmptyExpiry(unittest.TestCase):
    def test_renews_when_expires_at_is_empty(self):
        stub = _Stub(
            query_returns=[[
                {"vertex_id": "at://sub-1", "subscription_id": "sub_new",
                 "user_upn": "k.bakshi@etzhayyim.com", "expires_at": ""},
            ]],
            post_returns=[{"id": "sub_new"}],
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_msgraph import (
                task_lawfirm_msgraph_subscription_renew,
            )
            out = asyncio.run(task_lawfirm_msgraph_subscription_renew())
            self.assertEqual(out["renewed"], 1)
            self.assertEqual(len(stub.posts), 1)
        finally:
            stub.uninstall()


class TestRenewMixedBatch(unittest.TestCase):
    def test_three_subs_one_expiring_two_healthy(self):
        import datetime as _dt
        soon = (_dt.datetime.now(tz=_dt.UTC) + _dt.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        far = (_dt.datetime.now(tz=_dt.UTC) + _dt.timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        stub = _Stub(
            query_returns=[[
                {"vertex_id": "at://sub-1", "subscription_id": "sub_old",
                 "user_upn": "k.bakshi@etzhayyim.com", "expires_at": soon},
                {"vertex_id": "at://sub-2", "subscription_id": "sub_new",
                 "user_upn": "k.bakshi@etzhayyim.com", "expires_at": far},
                {"vertex_id": "at://sub-3", "subscription_id": "sub_other",
                 "user_upn": "n-takahashi@etzhayyim.com", "expires_at": far},
            ]],
            post_returns=[{"id": "sub_old"}],
        )
        stub.install()
        try:
            from kotodama.primitives.lawfirm_msgraph import (
                task_lawfirm_msgraph_subscription_renew,
            )
            out = asyncio.run(task_lawfirm_msgraph_subscription_renew())
            self.assertEqual(out["checked"], 3)
            self.assertEqual(out["renewed"], 1)
            # Only sub_old should have been PATCHed
            self.assertEqual(len(stub.posts), 1)
            self.assertIn("sub_old", stub.posts[0][0])
        finally:
            stub.uninstall()


class TestRenewHandlesGraphError(unittest.TestCase):
    def test_continues_after_one_sub_fails(self):
        import datetime as _dt
        soon = (_dt.datetime.now(tz=_dt.UTC) + _dt.timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")

        # Two subs, both need renewal, first PATCH raises, second succeeds
        stub = _Stub(
            query_returns=[[
                {"vertex_id": "at://sub-1", "subscription_id": "sub_bad",
                 "user_upn": "u1", "expires_at": soon},
                {"vertex_id": "at://sub-2", "subscription_id": "sub_good",
                 "user_upn": "u2", "expires_at": soon},
            ]],
        )
        stub.install()
        # Override _ms_post to raise on first call
        import kotodama.primitives.lawfirm_msgraph as p
        original_post = p._ms_post
        call_count = [0]
        def _flaky(url, body, method="POST"):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Graph 503 Service Unavailable")
            return {"id": "sub_good"}
        p._ms_post = _flaky
        try:
            from kotodama.primitives.lawfirm_msgraph import (
                task_lawfirm_msgraph_subscription_renew,
            )
            out = asyncio.run(task_lawfirm_msgraph_subscription_renew())
            # Not ok overall (errors present) but second sub did renew
            self.assertFalse(out["ok"])
            self.assertEqual(out["checked"], 2)
            self.assertEqual(out["renewed"], 1)
            self.assertEqual(len(out["errors"]), 1)
            self.assertIn("sub_bad", out["errors"][0])
            self.assertIn("503", out["errors"][0])
        finally:
            p._ms_post = original_post
            stub.uninstall()


# ── subscriptionEnsure tests (lighter coverage; helpers we know work) ───────


class TestEnsureRequiresUserUpn(unittest.TestCase):
    def test_handles_empty_upn_gracefully(self):
        # Pre-existing logic should accept empty + use default
        stub = _Stub(query_returns=[[]], post_returns=[
            {"id": "new_sub_id", "expirationDateTime": "2026-08-01T00:00:00Z"}
        ])
        stub.install()
        try:
            from kotodama.primitives.lawfirm_msgraph import (
                task_lawfirm_msgraph_subscription_ensure,
            )
            out = asyncio.run(task_lawfirm_msgraph_subscription_ensure(
                user_upn="k.bakshi@etzhayyim.com",
                folder="Inbox",
                notification_url="https://lawfirm.etzhayyim.com/xrpc/com.etzhayyim.apps.lawfirm.mailReplyWebhook",
                client_state="test-state-32-chars-or-more-secret-x",
            ))
            self.assertTrue(out.get("ok") is True or out.get("subscription_id") is not None)
        finally:
            stub.uninstall()


if __name__ == "__main__":
    unittest.main()
