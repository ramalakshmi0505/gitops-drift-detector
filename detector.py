"""
GitOps Drift Detector — Core
Connects to ArgoCD and detects applications that are out of sync,
degraded, or have drifted from their Git source of truth.
"""

import requests
import urllib3
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


HEALTH_COLORS = {
    "Healthy":     "✅",
    "Progressing": "🔄",
    "Degraded":    "❌",
    "Suspended":   "⏸",
    "Missing":     "❓",
    "Unknown":     "❓",
}

SYNC_COLORS = {
    "Synced":       "✅",
    "OutOfSync":    "⚠️",
    "Unknown":      "❓",
}


@dataclass
class AppDrift:
    name: str
    namespace: str
    project: str
    sync_status: str
    health_status: str
    repo_url: str
    target_revision: str
    cluster: str
    drift_reason: str
    last_synced: Optional[str] = None
    message: Optional[str] = None
    is_drifted: bool = False


@dataclass
class DriftReport:
    cluster_url: str
    scanned_at: str
    total_apps: int
    drifted_apps: list = field(default_factory=list)
    healthy_apps: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def _get_token(argocd_url: str, username: str, password: str, verify_ssl: bool) -> str:
    resp = requests.post(
        f"{argocd_url}/api/v1/session",
        json={"username": username, "password": password},
        verify=verify_ssl,
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()["token"]


def _fetch_apps(argocd_url: str, token: str, verify_ssl: bool) -> list:
    resp = requests.get(
        f"{argocd_url}/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        verify=verify_ssl,
        timeout=30
    )
    resp.raise_for_status()
    return resp.json().get("items", [])


def _parse_app(app: dict) -> AppDrift:
    meta    = app.get("metadata", {})
    spec    = app.get("spec", {})
    status  = app.get("status", {})
    src     = spec.get("source", {})
    dest    = spec.get("destination", {})

    sync_status   = status.get("sync", {}).get("status", "Unknown")
    health_status = status.get("health", {}).get("status", "Unknown")
    message       = status.get("operationState", {}).get("message", "")
    last_synced   = status.get("operationState", {}).get("finishedAt", None)

    reasons = []
    if sync_status == "OutOfSync":
        reasons.append("app is out of sync with Git source")
    if health_status == "Degraded":
        reasons.append("health status is Degraded")
    if health_status == "Missing":
        reasons.append("resources are missing from cluster")
    if sync_status == "Unknown" or health_status == "Unknown":
        reasons.append("status is Unknown — ArgoCD may have lost contact")

    is_drifted = bool(reasons)

    return AppDrift(
        name=meta.get("name", "unknown"),
        namespace=meta.get("namespace", "argocd"),
        project=spec.get("project", "default"),
        sync_status=sync_status,
        health_status=health_status,
        repo_url=src.get("repoURL", ""),
        target_revision=src.get("targetRevision", "HEAD"),
        cluster=dest.get("server", dest.get("name", "in-cluster")),
        drift_reason="; ".join(reasons) if reasons else "none",
        last_synced=last_synced,
        message=message[:200] if message else None,
        is_drifted=is_drifted,
    )


def scan(
    argocd_url: str,
    username: str,
    password: str,
    token: Optional[str] = None,
    verify_ssl: bool = True,
    project_filter: Optional[str] = None,
) -> DriftReport:
    """
    Connect to ArgoCD and return a DriftReport.

    Args:
        argocd_url:     ArgoCD server URL e.g. https://argocd.example.com
        username:       ArgoCD username (ignored if token provided)
        password:       ArgoCD password (ignored if token provided)
        token:          Optional bearer token (skips login)
        verify_ssl:     Verify TLS certificates (set False for self-signed)
        project_filter: Optional ArgoCD project name to filter by
    """
    print(f"  Connecting to ArgoCD at {argocd_url}...")

    if not token:
        token = _get_token(argocd_url, username, password, verify_ssl)
        print("  Authenticated successfully.")

    raw_apps = _fetch_apps(argocd_url, token, verify_ssl)
    print(f"  Found {len(raw_apps)} application(s).")

    if project_filter:
        raw_apps = [a for a in raw_apps if a.get("spec", {}).get("project") == project_filter]
        print(f"  Filtered to {len(raw_apps)} app(s) in project '{project_filter}'.")

    drifted = []
    healthy = []

    for app in raw_apps:
        parsed = _parse_app(app)
        if parsed.is_drifted:
            drifted.append(parsed)
        else:
            healthy.append(parsed)

    report = DriftReport(
        cluster_url=argocd_url,
        scanned_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        total_apps=len(raw_apps),
        drifted_apps=drifted,
        healthy_apps=healthy,
        summary={
            "total":   len(raw_apps),
            "drifted": len(drifted),
            "healthy": len(healthy),
            "drift_rate_pct": round(len(drifted) / len(raw_apps) * 100, 1) if raw_apps else 0,
        }
    )

    return report
