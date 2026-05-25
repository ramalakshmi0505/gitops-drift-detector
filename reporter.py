"""
GitOps Drift Detector — Reporters
Terminal, JSON, Slack webhook, and Email notifications.
"""

import json
import os
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import asdict

from .detector import DriftReport, HEALTH_COLORS, SYNC_COLORS

RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"


# ── TERMINAL ──────────────────────────────────────────────────────────────────

def print_report(report: DriftReport):
    print()
    print(BOLD + CYAN + "━" * 65 + RESET)
    print(BOLD + "  🔍  GitOps Drift Detector" + RESET)
    print(BOLD + CYAN + "━" * 65 + RESET)
    print(f"  ArgoCD   : {report.cluster_url}")
    print(f"  Scanned  : {report.scanned_at}")
    print(f"  Total    : {report.total_apps} applications")
    print(CYAN + "━" * 65 + RESET)

    s = report.summary
    drift_color = RED if s["drifted"] > 0 else GREEN
    print()
    print(BOLD + "  SUMMARY" + RESET)
    print(f"  Total apps    : {BOLD}{s['total']}{RESET}")
    print(f"  Healthy       : {GREEN}{BOLD}{s['healthy']}{RESET}")
    print(f"  Drifted       : {drift_color}{BOLD}{s['drifted']}{RESET}")
    print(f"  Drift rate    : {drift_color}{BOLD}{s['drift_rate_pct']}%{RESET}")

    if report.drifted_apps:
        print()
        print(BOLD + RED + "  DRIFTED APPLICATIONS" + RESET)
        print(CYAN + "  " + "─" * 63 + RESET)
        for app in report.drifted_apps:
            sync_icon   = SYNC_COLORS.get(app.sync_status, "❓")
            health_icon = HEALTH_COLORS.get(app.health_status, "❓")
            print(f"\n  {BOLD}{app.name}{RESET}  [{app.project}]")
            print(f"  Sync    : {sync_icon}  {app.sync_status}")
            print(f"  Health  : {health_icon}  {app.health_status}")
            print(f"  Repo    : {GRAY}{app.repo_url}@{app.target_revision}{RESET}")
            print(f"  Cluster : {app.cluster}")
            print(f"  {YELLOW}⚠  {app.drift_reason}{RESET}")
            if app.message:
                print(f"  {GRAY}Msg: {app.message}{RESET}")
    else:
        print()
        print(GREEN + BOLD + "  ✅  All applications are in sync. No drift detected." + RESET)

    if report.healthy_apps:
        print()
        print(BOLD + "  HEALTHY APPLICATIONS" + RESET)
        print(CYAN + "  " + "─" * 63 + RESET)
        for app in report.healthy_apps:
            print(f"  ✅  {app.name:<35} [{app.project}]")

    print()
    print(CYAN + "━" * 65 + RESET)
    print()


# ── JSON ──────────────────────────────────────────────────────────────────────

def save_json_report(report: DriftReport, output_dir: str = "reports") -> str:
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(
        output_dir,
        f"drift-report-{datetime.utcnow().strftime('%Y%m%d-%H%M')}.json"
    )

    def _serialise(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        raise TypeError(f"Not serialisable: {type(obj)}")

    data = {
        "cluster_url":  report.cluster_url,
        "scanned_at":   report.scanned_at,
        "summary":      report.summary,
        "drifted_apps": [asdict(a) for a in report.drifted_apps],
        "healthy_apps": [asdict(a) for a in report.healthy_apps],
    }

    with open(filename, "w") as f:
        json.dump(data, f, indent=2, default=str)

    return filename


# ── SLACK ─────────────────────────────────────────────────────────────────────

def send_slack_alert(report: DriftReport, webhook_url: str):
    s = report.summary

    if s["drifted"] == 0:
        color = "good"
        title = f"✅ GitOps Drift Detector — All {s['total']} apps healthy"
        text  = f"Scanned at {report.scanned_at}. No drift detected."
    else:
        color = "danger"
        title = f"⚠️ GitOps Drift Detected — {s['drifted']} of {s['total']} apps drifted"
        text  = f"Scanned at {report.scanned_at}. Drift rate: {s['drift_rate_pct']}%"

    fields = []
    for app in report.drifted_apps[:10]:  # cap at 10 for Slack readability
        fields.append({
            "title": app.name,
            "value": f"Sync: {app.sync_status} | Health: {app.health_status}\n_{app.drift_reason}_",
            "short": False
        })

    payload = {
        "attachments": [{
            "color":    color,
            "title":    title,
            "text":     text,
            "fields":   fields,
            "footer":   "gitops-drift-detector",
            "ts":       int(datetime.utcnow().timestamp()),
        }]
    }

    resp = requests.post(webhook_url, json=payload, timeout=10)
    resp.raise_for_status()
    print(f"  Slack alert sent.")


# ── EMAIL ─────────────────────────────────────────────────────────────────────

def send_email_alert(
    report: DriftReport,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    from_addr: str,
    to_addrs: list,
    use_tls: bool = True,
):
    s = report.summary

    if s["drifted"] == 0:
        subject = f"[GitOps] All clear — {s['total']} apps healthy ({report.scanned_at})"
    else:
        subject = f"[GitOps] DRIFT ALERT — {s['drifted']}/{s['total']} apps drifted ({report.scanned_at})"

    # Plain text body
    lines = [
        "GitOps Drift Detector Report",
        "=" * 40,
        f"ArgoCD   : {report.cluster_url}",
        f"Scanned  : {report.scanned_at}",
        f"Total    : {s['total']} apps",
        f"Healthy  : {s['healthy']}",
        f"Drifted  : {s['drifted']}",
        f"Drift %  : {s['drift_rate_pct']}%",
        "",
    ]

    if report.drifted_apps:
        lines.append("DRIFTED APPLICATIONS")
        lines.append("-" * 40)
        for app in report.drifted_apps:
            lines += [
                f"App      : {app.name}",
                f"Project  : {app.project}",
                f"Sync     : {app.sync_status}",
                f"Health   : {app.health_status}",
                f"Reason   : {app.drift_reason}",
                f"Repo     : {app.repo_url}@{app.target_revision}",
                "",
            ]
    else:
        lines.append("All applications are healthy. No action required.")

    body = "\n".join(lines)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = ", ".join(to_addrs)
    msg.attach(MIMEText(body, "plain"))

    if use_tls:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port)

    server.login(smtp_user, smtp_password)
    server.sendmail(from_addr, to_addrs, msg.as_string())
    server.quit()
    print(f"  Email alert sent to {', '.join(to_addrs)}.")
