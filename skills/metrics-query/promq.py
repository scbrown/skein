#!/usr/bin/env python3
"""promq — query Prometheus / Alertmanager and report an honest outcome.

Stdlib only. No packages, no lockfile.

The whole point of this script is that it does NOT round outcomes up. A query
that errored, a query that matched nothing, and an endpoint that was not there
are three different answers, and each gets its own exit code:

    0   OK      the query succeeded AND matched at least one series
    2   EMPTY   the query succeeded and matched NOTHING (not an error, not "healthy")
    1   ERROR   the API said status=error, or returned a non-2xx
    3   UNREACH the endpoint could not be reached at all

`EMPTY` is separated from `OK` on purpose. `up == 0` returning no rows is the
single most common false "all clear" in monitoring: it reads as "nothing is
down" and is indistinguishable from "you misspelled the metric" or "the target
vanished from service discovery entirely". A caller that cannot tell those apart
should not be reporting green.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

OK, ERROR, EMPTY, UNREACH = 0, 1, 2, 3

TIMEOUT = float(os.environ.get("PROM_TIMEOUT", "10"))


def _get(base: str, path: str, params: dict[str, str] | None = None) -> tuple[int, object]:
    """GET base+path. Returns (http_status, parsed_body_or_raw_text).

    Raises URLError/socket errors to the caller — those mean UNREACH, which is a
    different thing from an API-level error and must not be flattened into one.
    """
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    token = os.environ.get("PROM_BEARER_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        # 400/422 carry a JSON error body that we WANT — read it, don't discard it.
        raw = e.read().decode("utf-8", "replace")
        status = e.code
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def _fail(msg: str, code: int) -> int:
    sys.stdout.flush()
    print(f"{'ERROR':8s} {msg}", file=sys.stderr)
    return code


def _note(msg: str) -> None:
    """Commentary goes to stderr so `--json` piping stays clean — but flush stdout
    first, or the note overtakes the rows it is commenting on."""
    sys.stdout.flush()
    print(msg, file=sys.stderr)


def _series_count(data: dict) -> int:
    rt = data.get("resultType")
    result = data.get("result") or []
    if rt in ("vector", "matrix"):
        return len(result)
    if rt in ("scalar", "string"):
        return 1 if result else 0
    return len(result) if isinstance(result, list) else 0


def cmd_query(args: argparse.Namespace) -> int:
    base = args.prom
    if not base:
        return _fail("PROM_URL is not set. Nothing was queried.", UNREACH)

    params = {"query": args.expr}
    path = "/api/v1/query"
    if args.start:
        path = "/api/v1/query_range"
        params.update({"start": args.start, "end": args.end or "now", "step": args.step})
    if args.at:
        params["time"] = args.at

    try:
        status, body = _get(base, path, params)
    except Exception as e:  # noqa: BLE001 — unreachable is a first-class outcome
        return _fail(f"{base} unreachable: {e}", UNREACH)

    if not isinstance(body, dict):
        return _fail(f"HTTP {status}: non-JSON response from {base}{path}", ERROR)

    # The ONLY success signal. A 400/422 also parses as JSON and also has a
    # "data" key shape a careless client will happily index into and get [].
    if body.get("status") != "success":
        return _fail(
            f"HTTP {status} {body.get('errorType', 'error')}: {body.get('error', body)}",
            ERROR,
        )

    data = body.get("data") or {}
    n = _series_count(data)

    if args.json:
        print(json.dumps(body, indent=2))
    else:
        for item in data.get("result") or []:
            metric = item.get("metric") or {}
            name = metric.pop("__name__", "")
            labels = ",".join(f'{k}="{v}"' for k, v in sorted(metric.items()))
            sel = f"{name}{{{labels}}}" if labels else (name or "{}")
            if "value" in item:
                print(f"{item['value'][1]:>16}  {sel}")
            else:  # matrix
                vals = item.get("values") or []
                last = vals[-1][1] if vals else "-"
                print(f"{last:>16}  {sel}   ({len(vals)} samples)")

    if n == 0:
        _note(
            f"EMPTY    query succeeded and matched 0 series: {args.expr}\n"
            f"         This is NOT the same as healthy. Before reporting green, run the\n"
            f"         selector bare (drop the comparison) and confirm the series exists."
        )
        return EMPTY
    return OK


def cmd_targets(args: argparse.Namespace) -> int:
    base = args.prom
    if not base:
        return _fail("PROM_URL is not set. Nothing was queried.", UNREACH)
    try:
        status, body = _get(base, "/api/v1/targets", {"state": "active"})
    except Exception as e:  # noqa: BLE001
        return _fail(f"{base} unreachable: {e}", UNREACH)
    if not isinstance(body, dict) or body.get("status") != "success":
        return _fail(f"HTTP {status}: {body}", ERROR)

    targets = (body.get("data") or {}).get("activeTargets") or []
    if args.json:
        print(json.dumps(targets, indent=2))
        return OK if targets else EMPTY

    down = [t for t in targets if t.get("health") != "up"]
    for t in targets if args.all else down:
        labels = t.get("labels") or {}
        who = labels.get("job", "?") + "/" + labels.get("instance", "?")
        line = f"{t.get('health', '?'):8s} {who}"
        if t.get("lastError"):
            line += f"   lastError={t['lastError']}"
        print(line)

    _note(
        f"\n{len(targets)} active target(s), {len(down)} not up.\n"
        f"NOTE: this lists targets service discovery CURRENTLY knows about. A target\n"
        f"      that was dropped from discovery is absent here and absent from `up` —\n"
        f"      it cannot appear as down because it cannot appear at all. Compare this\n"
        f"      list against your own inventory; the endpoint cannot do it for you."
    )
    if not targets:
        return EMPTY
    return OK


def cmd_alerts(args: argparse.Namespace) -> int:
    base = args.alertmanager
    if not base:
        return _fail("ALERTMANAGER_URL is not set. Nothing was queried.", UNREACH)

    # Alertmanager v2 defaults silenced/inhibited to TRUE. Ask explicitly, always:
    # inheriting the default is how "12 alerts firing" turns out to be 3 firing
    # and 9 that someone silenced last month.
    params = {
        "active": "true",
        "silenced": "true" if args.include_silenced else "false",
        "inhibited": "true" if args.include_inhibited else "false",
        "unprocessed": "false",
    }
    try:
        status, body = _get(base, "/api/v2/alerts", params)
    except Exception as e:  # noqa: BLE001
        return _fail(f"{base} unreachable: {e}", UNREACH)
    if status >= 300:
        return _fail(f"HTTP {status}: {body}", ERROR)
    if not isinstance(body, list):
        return _fail(f"expected a JSON array from /api/v2/alerts, got {type(body).__name__}", ERROR)

    if args.json:
        print(json.dumps(body, indent=2))
    else:
        for a in body:
            labels = a.get("labels") or {}
            st = (a.get("status") or {}).get("state", "?")
            print(
                f"{labels.get('severity', '-'):8s} {st:11s} "
                f"{labels.get('alertname', '?')}  {labels.get('instance', '')}"
            )

    _note(
        f"\n{len(body)} alert(s) "
        f"[silenced {'included' if args.include_silenced else 'EXCLUDED'}, "
        f"inhibited {'included' if args.include_inhibited else 'EXCLUDED'}]"
    )
    return OK if body else EMPTY


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="promq", description=__doc__.split("\n")[0])
    p.add_argument("--prom", default=os.environ.get("PROM_URL"))
    p.add_argument("--alertmanager", default=os.environ.get("ALERTMANAGER_URL"))
    p.add_argument("--json", action="store_true", help="raw JSON instead of a table")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("query", help="run a PromQL query")
    q.add_argument("expr")
    q.add_argument("--at", help="instant query at this time (RFC3339 or unix ts)")
    q.add_argument("--start", help="range query start (switches to query_range)")
    q.add_argument("--end", help="range query end")
    q.add_argument("--step", default="60s")
    q.set_defaults(func=cmd_query)

    t = sub.add_parser("targets", help="scrape targets and their health")
    t.add_argument("--all", action="store_true", help="list every target, not just the unhealthy")
    t.set_defaults(func=cmd_targets)

    a = sub.add_parser("alerts", help="alerts from Alertmanager")
    a.add_argument("--include-silenced", action="store_true")
    a.add_argument("--include-inhibited", action="store_true")
    a.set_defaults(func=cmd_alerts)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
