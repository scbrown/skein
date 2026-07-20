"""Proof that every promq outcome can fire — especially EMPTY.

skein convention: a check that has never returned every one of its outcomes is
not a check. The outcome that matters here is EMPTY. A Prometheus query that
matched nothing returns HTTP 200 with `{"status":"success","data":{"result":[]}}`
— byte-for-byte the shape of a healthy answer. If EMPTY cannot be observed
separately from OK, then "nothing is down" and "you misspelled the metric" are
the same string, and the skill is lying by construction.

Stdlib unittest — no pytest, no network, no Prometheus. Run: python3 -m unittest
"""
import unittest

import promq


class Endpoint:
    """Swap the HTTP layer for a canned response, so each command is a pure
    function of (status, body). `raises` simulates an unreachable endpoint,
    which must NOT be flattened into an API error."""

    def __init__(self, status=200, body=None, raises=None):
        self.status, self.body, self.raises = status, body, raises
        self.calls = []

    def __enter__(self):
        self._get = promq._get

        def fake(base, path, params=None):
            self.calls.append((base, path, params or {}))
            if self.raises:
                raise self.raises
            return self.status, self.body

        promq._get = fake
        return self

    def __exit__(self, *a):
        promq._get = self._get


def vector(*samples):
    return {
        "status": "success",
        "data": {"resultType": "vector", "result": list(samples)},
    }


SAMPLE = {"metric": {"__name__": "up", "job": "node", "instance": "h1:9100"}, "value": [1, "0"]}


class TestQueryOutcomes(unittest.TestCase):
    def run_query(self, **kw):
        with Endpoint(**kw) as ep:
            rc = promq.main(["--prom", "http://p.example.com", "query", "up == 0"])
        return rc, ep

    def test_match_is_ok(self):
        rc, _ = self.run_query(body=vector(SAMPLE))
        self.assertEqual(rc, promq.OK)

    def test_zero_series_is_EMPTY_not_ok(self):
        """The whole reason this script exists."""
        rc, _ = self.run_query(body=vector())
        self.assertEqual(rc, promq.EMPTY)
        self.assertNotEqual(rc, promq.OK)

    def test_api_error_is_ERROR_not_empty(self):
        """A 422 body also has a parseable shape. It must not read as 'no results'."""
        rc, _ = self.run_query(
            status=422,
            body={"status": "error", "errorType": "bad_data", "error": "parse error: unexpected {"},
        )
        self.assertEqual(rc, promq.ERROR)

    def test_unreachable_is_UNREACH_not_error(self):
        rc, _ = self.run_query(raises=OSError("connection refused"))
        self.assertEqual(rc, promq.UNREACH)

    def test_unset_url_sends_nothing_and_says_so(self):
        with Endpoint(body=vector(SAMPLE)) as ep:
            rc = promq.main(["--prom", "", "query", "up"])
        self.assertEqual(rc, promq.UNREACH)
        self.assertEqual(ep.calls, [], "must not issue a request with no endpoint configured")

    def test_range_query_uses_query_range(self):
        with Endpoint(body={"status": "success", "data": {"resultType": "matrix", "result": []}}) as ep:
            promq.main(["--prom", "http://p.example.com", "query", "up", "--start", "now-1h"])
        self.assertEqual(ep.calls[0][1], "/api/v1/query_range")
        self.assertIn("step", ep.calls[0][2])


class TestAlerts(unittest.TestCase):
    def test_silenced_and_inhibited_are_excluded_by_default(self):
        """Alertmanager v2 defaults these to true. Inheriting that default is how
        an alert someone silenced last month gets counted as firing today."""
        with Endpoint(body=[]) as ep:
            promq.main(["--alertmanager", "http://a.example.com", "alerts"])
        params = ep.calls[0][2]
        self.assertEqual(params["silenced"], "false")
        self.assertEqual(params["inhibited"], "false")
        self.assertEqual(params["active"], "true")

    def test_opt_in_includes_them(self):
        with Endpoint(body=[]) as ep:
            promq.main(
                ["--alertmanager", "http://a.example.com", "alerts",
                 "--include-silenced", "--include-inhibited"]
            )
        params = ep.calls[0][2]
        self.assertEqual(params["silenced"], "true")
        self.assertEqual(params["inhibited"], "true")

    def test_no_alerts_is_EMPTY(self):
        with Endpoint(body=[]):
            rc = promq.main(["--alertmanager", "http://a.example.com", "alerts"])
        self.assertEqual(rc, promq.EMPTY)

    def test_alerts_present_is_OK(self):
        alert = {"labels": {"alertname": "InstanceDown", "severity": "critical"},
                 "status": {"state": "active"}}
        with Endpoint(body=[alert]):
            rc = promq.main(["--alertmanager", "http://a.example.com", "alerts"])
        self.assertEqual(rc, promq.OK)


class TestTargets(unittest.TestCase):
    def test_non_success_is_ERROR(self):
        with Endpoint(status=500, body={"status": "error", "error": "boom"}):
            rc = promq.main(["--prom", "http://p.example.com", "targets"])
        self.assertEqual(rc, promq.ERROR)

    def test_targets_listed(self):
        body = {
            "status": "success",
            "data": {"activeTargets": [
                {"health": "down", "labels": {"job": "node", "instance": "h1:9100"},
                 "lastError": "context deadline exceeded"},
            ]},
        }
        with Endpoint(body=body):
            rc = promq.main(["--prom", "http://p.example.com", "targets"])
        self.assertEqual(rc, promq.OK)


if __name__ == "__main__":
    unittest.main()
