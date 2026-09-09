#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin

import httpx


def _request(url: str, timeout_seconds: float) -> tuple[bool, float]:
    started = time.perf_counter()
    try:
        response = httpx.get(url, timeout=timeout_seconds, follow_redirects=False)
        ok = 200 <= response.status_code < 300
    except httpx.HTTPError:
        ok = False
    return ok, (time.perf_counter() - started) * 1000


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_alerts(path: Path, max_age_hours: float) -> list[str]:
    if not path.is_file() or path.stat().st_size <= 0:
        return ["backup_missing_or_empty"]
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    alerts: list[str] = []
    if age_hours > max_age_hours:
        alerts.append("backup_stale")
    checksum_path = Path(f"{path}.sha256")
    if not checksum_path.is_file():
        alerts.append("backup_checksum_missing")
        return alerts
    expected = checksum_path.read_text(encoding="utf-8").strip().split()[0].lower()
    if expected != _sha256(path):
        alerts.append("backup_checksum_mismatch")
    return alerts


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run bounded HajiriFlow readiness, backup-health, and HTTP load-smoke checks."
        )
    )
    parser.add_argument("--base-url", required=True, help="Staging or production-like base URL.")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--p95-ms", type=float, default=1000.0)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--backup-path", type=Path)
    parser.add_argument("--max-backup-age-hours", type=float, default=26.0)
    args = parser.parse_args()

    if not 1 <= args.requests <= 500:
        parser.error("--requests must be between 1 and 500")
    if not 1 <= args.concurrency <= 25:
        parser.error("--concurrency must be between 1 and 25")
    if args.p95_ms <= 0 or args.timeout_seconds <= 0:
        parser.error("latency and timeout thresholds must be positive")
    if args.max_backup_age_hours <= 0:
        parser.error("--max-backup-age-hours must be positive")

    base_url = args.base_url.rstrip("/") + "/"
    health_url = urljoin(base_url, "health")
    ready_url = urljoin(base_url, "ready")
    health_ok, health_ms = _request(health_url, args.timeout_seconds)
    ready_ok, ready_ms = _request(ready_url, args.timeout_seconds)

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        samples = list(
            pool.map(
                lambda _: _request(health_url, args.timeout_seconds),
                range(args.requests),
            )
        )
    successful = [duration for ok, duration in samples if ok]
    failed_requests = len(samples) - len(successful)
    p95_ms = _p95(successful)

    alerts: list[str] = []
    if not health_ok:
        alerts.append("web_health_unavailable")
    if not ready_ok:
        alerts.append("database_unavailable")
    if failed_requests:
        alerts.append("load_smoke_request_failures")
    if p95_ms > args.p95_ms:
        alerts.append("load_smoke_p95_exceeded")
    if args.backup_path is not None:
        alerts.extend(_backup_alerts(args.backup_path, args.max_backup_age_hours))

    report = {
        "ok": not alerts,
        "health": {"ok": health_ok, "latency_ms": round(health_ms, 2)},
        "ready": {"ok": ready_ok, "latency_ms": round(ready_ms, 2)},
        "load_smoke": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "failed": failed_requests,
            "p95_ms": round(p95_ms, 2),
            "p95_limit_ms": args.p95_ms,
        },
        "backup_checked": args.backup_path is not None,
        "alerts": sorted(set(alerts)),
    }
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
