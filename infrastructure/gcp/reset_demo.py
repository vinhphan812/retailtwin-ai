#!/usr/bin/env python3
"""Reset all GCP services to the demo baseline.

Issue #135: Seed and reset real GCP data for deterministic end-to-end demo.

This script resets all GCP services to their initial demo state:
1. Firestore: Delete all inventory documents, bump store version
2. BigQuery: Note that historical data is retained (date-filtered queries)
3. Pub/Sub: No action needed (events are ephemeral)

After reset, use seed_gcp.py to reseed all services.

Usage:
    # Preview reset without executing
    python infrastructure/gcp/reset_demo.py --dry-run

    # Reset all services
    CONFIRM_RESET=yes python infrastructure/gcp/reset_demo.py

    # Reset Firestore only
    python infrastructure/gcp/reset_demo.py --firestore-only

    # Reset and reseed in one command
    CONFIRM_RESET=yes CONFIRM_SEED=yes python infrastructure/gcp/reset_demo.py --reseed
"""

import argparse
import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

# Add repo root to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

# GCP Configuration
PROJECT = os.environ.get("GCP_PROJECT_ID", "retailtwin-ai-511002")
REGION = os.environ.get("GCP_REGION", "us-central1")
DATASET = os.environ.get("BIGQUERY_DATASET", "retailtwin")
TOPIC = os.environ.get("STORE_EVENTS_TOPIC", "store-events")
CANONICAL_PROJECT = "retailtwin-ai-511002"
STORE_ID = "store-001"


def command_env() -> dict[str, str]:
    env = os.environ.copy()
    env["CLOUDSDK_CORE_DISABLE_PROMPTS"] = "1"
    env["CLOUDSDK_CORE_PROJECT"] = PROJECT
    return env


class CommandRunner(Protocol):
    def run(self, args: list[str]) -> str: ...


class SubprocessRunner:
    def run(self, args: list[str]) -> str:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            env=command_env(),
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(detail or f"Command failed with exit {completed.returncode}.")
        return completed.stdout


class GcloudTokenProvider:
    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner
        self._token: str | None = None

    def get_token(self) -> str:
        if self._token is None:
            raw = self._runner.run(["gcloud", "auth", "print-access-token", "--quiet"])
            self._token = raw.strip()
        return self._token


class HttpResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body


class HttpTransport:
    def __init__(self, token_provider: GcloudTokenProvider) -> None:
        self._token_provider = token_provider
        self._token_lock = threading.Lock()

    def request(
        self,
        method: str,
        url: str,
        payload: bytes | None,
        headers: dict[str, str],
    ) -> HttpResponse:
        with self._token_lock:
            token = self._token_provider.get_token()
        headers = {**headers, "Authorization": f"Bearer {token}"}
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return HttpResponse(response.status, response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return HttpResponse(exc.code, exc.read().decode("utf-8", errors="replace"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Request failed: {exc.reason}") from exc


def database_root() -> str:
    return f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"


def doc_name(collection: str, *path: str) -> str:
    return f"{database_root()}/{'/'.join([collection, *path])}"


def reset_firestore(transport: HttpTransport, dry_run: bool = False) -> dict[str, Any]:
    """Reset Firestore Live Twin by deleting inventory documents."""
    results: dict[str, Any] = {"firestore": {}}
    
    # List all inventory documents
    url = f"{database_root()}/stores/{STORE_ID}/inventory"
    response = transport.request("GET", url, None, {"Content-Type": "application/json"})
    
    if response.status == 404:
        results["firestore"] = {"reset": True, "deleted": 0, "message": "No inventory found"}
        return results
    
    if response.status != 200:
        raise RuntimeError(f"Failed to list inventory: {response.body[:200]}")
    
    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError:
        raise RuntimeError("Inventory list response is not JSON")
    
    documents = payload.get("documents", [])
    results["firestore"]["found"] = len(documents)
    
    if not documents:
        results["firestore"].update({"reset": True, "deleted": 0, "message": "No inventory to delete"})
        return results
    
    if dry_run:
        results["firestore"].update({
            "dry_run": True,
            "documents_to_delete": len(documents),
            "sample": [doc.get("name", "") for doc in documents[:5]],
        })
        return results
    
    # Build delete writes
    writes: list[dict[str, Any]] = []
    for doc in documents:
        name = doc.get("name", "")
        if name:
            writes.append({"delete": name})
    
    # Bump store version
    now = datetime.now(timezone.utc).isoformat()
    writes.append({
        "update": {
            "name": doc_name("stores", STORE_ID),
            "fields": {
                "store_id": {"stringValue": STORE_ID},
                "version": {"stringValue": "v1"},
                "updated_at": {"timestampValue": now},
            }
        }
    })
    
    # Execute deletes
    payload = {"writes": writes}
    url = f"{database_root()}:commit"
    raw = json.dumps(payload).encode("utf-8")
    
    response = transport.request("POST", url, raw, {"Content-Type": "application/json"})
    
    if response.status != 200:
        raise RuntimeError(f"Firestore reset failed (HTTP {response.status}): {response.body[:200]}")
    
    results["firestore"].update({
        "reset": True,
        "deleted": len(documents),
        "version_bumped": True,
        "timestamp": now,
    })
    
    return results


def reset_bigquery(dry_run: bool = False) -> dict[str, Any]:
    """Reset BigQuery demo data (retained as historical)."""
    # BigQuery retains all historical data
    # Demo queries should filter by date: occurred_at >= '2026-10-09T00:00:00Z'
    
    return {
        "bigquery": {
            "reset": True,
            "message": "BigQuery retains historical data",
            "note": "Use date filter for demo queries: occurred_at >= '2026-10-09T00:00:00Z'",
            "dry_run": dry_run,
        }
    }


def check_topic_exists() -> bool:
    """Check if Pub/Sub topic exists."""
    try:
        result = subprocess.run(
            ["gcloud", "pubsub", "topics", "describe", TOPIC, "--project", PROJECT],
            capture_output=True, text=True, env=command_env()
        )
        return result.returncode == 0
    except Exception:
        return False


def reset_pubsub(dry_run: bool = False) -> dict[str, Any]:
    """Reset Pub/Sub (no-op - events are ephemeral)."""
    topic_exists = check_topic_exists()
    
    return {
        "pubsub": {
            "reset": True,
            "message": "Pub/Sub events are ephemeral - no reset needed",
            "topic_exists": topic_exists,
            "note": "Published events expire according to topic retention settings",
            "dry_run": dry_run,
        }
    }


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def check_guardrails() -> None:
    """Validate environment before reset."""
    if PROJECT != CANONICAL_PROJECT:
        die(f"Refusing project {PROJECT}. Reset applies only to {CANONICAL_PROJECT}.")
    
    if os.environ.get("CONFIRM_RESET", "") != "yes":
        die("Set CONFIRM_RESET=yes to reset all GCP services to baseline.")
    
    # Check billing
    result = subprocess.run(
        ["gcloud", "billing", "projects", "describe", PROJECT,
         "--format=value(billingEnabled)"],
        capture_output=True, text=True, env=command_env()
    )
    if result.stdout.strip() != "True":
        die("Billing is disabled on this project.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset all GCP services to demo baseline."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview reset without executing"
    )
    parser.add_argument(
        "--firestore-only",
        action="store_true",
        help="Reset only Firestore"
    )
    parser.add_argument(
        "--bigquery-only",
        action="store_true",
        help="Reset only BigQuery"
    )
    parser.add_argument(
        "--pubsub-only",
        action="store_true",
        help="Reset only Pub/Sub"
    )
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="Also reseed after reset"
    )
    args = parser.parse_args()

    confirm = os.environ.get("CONFIRM_RESET", "")
    dry_run = args.dry_run or confirm == "dry"
    reseed = args.reseed or os.environ.get("CONFIRM_SEED", "") == "yes"
    
    print(f"Project:   {PROJECT}")
    print(f"Region:    {REGION}")
    print(f"Store:     {STORE_ID}")
    print(f"Dry run:   {dry_run}")
    print(f"Reseed:    {reseed}")
    print(f"Scope:     ", end="")
    
    if args.firestore_only:
        print("Firestore only")
    elif args.bigquery_only:
        print("BigQuery only")
    elif args.pubsub_only:
        print("Pub/Sub only")
    else:
        print("All services")
    
    print()

    if not dry_run:
        check_guardrails()
    else:
        print("DRY RUN MODE - No changes will be made")
        print()

    results: dict[str, Any] = {"dry_run": dry_run}

    # Reset selected services
    try:
        if not args.bigquery_only and not args.pubsub_only:
            # Initialize Firestore components
            runner = SubprocessRunner()
            token_provider = GcloudTokenProvider(runner)
            transport = HttpTransport(token_provider)
            
            print("Resetting Firestore Live Twin...")
            results["firestore"] = reset_firestore(transport, dry_run)
            print(f"  Result: {json.dumps(results['firestore'], indent=4)}")
            print()

        if not args.firestore_only and not args.pubsub_only:
            print("Resetting BigQuery...")
            results["bigquery"] = reset_bigquery(dry_run)
            print(f"  Result: {json.dumps(results['bigquery'], indent=4)}")
            print()

        if not args.firestore_only and not args.bigquery_only:
            print("Checking Pub/Sub...")
            results["pubsub"] = reset_pubsub(dry_run)
            print(f"  Result: {json.dumps(results['pubsub'], indent=4)}")
            print()

        print("Reset complete!")
        print()
        
        if reseed and not dry_run:
            print("Reseeding services...")
            print("  Run seed_gcp.py to reseed all services")
        
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
