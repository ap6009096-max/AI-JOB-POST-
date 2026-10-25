"""Production smoke checklist against a deployed (or local) stack.

Usage:
  set API_URL=https://aether-api-....run.app
  set WEB_URL=https://aether-web-....run.app
  python scripts/production_smoke.py

Exits non-zero if any required check fails.
"""

from __future__ import annotations

import os
import sys

import httpx

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
WEB_URL = os.environ.get("WEB_URL", "http://localhost:3000").rstrip("/")
TIMEOUT = float(os.environ.get("SMOKE_TIMEOUT", "20"))


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return ok


def main() -> int:
    failures = 0
    client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)

    try:
        api_health = client.get(f"{API_URL}/health")
        failures += not check("API /health", api_health.status_code == 200, api_health.text[:200])
    except Exception as exc:
        failures += not check("API /health", False, str(exc))

    try:
        web_health = client.get(f"{WEB_URL}/api/health")
        failures += not check("Web /api/health", web_health.status_code == 200, web_health.text[:200])
    except Exception as exc:
        failures += not check("Web /api/health", False, str(exc))

    checklist = [
        "Candidate registration",
        "Resume upload",
        "OCR (Document AI / Gemini)",
        "Gemini analysis",
        "Candidate JSON",
        "Profile update",
        "Company registration",
        "Manual job creation",
        "AI job creation",
        "Job JSON",
        "Portal Ranking Top 10 / 20 / 100",
        "Internet Talent Search",
        "GitHub sourcing",
        "LinkedIn authorized skip",
        "Portfolio",
        "Reddit permitted source",
        "External Candidate JSON",
        "Internet Ranking",
        "Match Details",
    ]
    print("\nManual / integration checklist (run authenticated E2E against the stack):")
    for item in checklist:
        print(f"  [ ] {item}")

    print(f"\nAutomated health failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
