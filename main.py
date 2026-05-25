#!/usr/bin/env python3
"""
gitops-drift-detector — CLI

Usage examples:

  # Basic scan (username/password)
  python main.py --url https://argocd.example.com --username admin --password secret

  # Using a bearer token
  python main.py --url https://argocd.example.com --token <argocd-token>

  # Filter by ArgoCD project
  python main.py --url https://argocd.example.com --token <token> --project production

  # Skip TLS verification (self-signed certs)
  python main.py --url https://argocd.example.com --token <token> --no-verify-ssl

  # Send Slack alert
  python main.py --url https://argocd.example.com --token <token> \\
    --slack-webhook https://hooks.slack.com/services/xxx/yyy/zzz

  # Send email alert
  python main.py --url https://argocd.example.com --token <token> \\
    --smtp-host smtp.gmail.com --smtp-port 587 \\
    --smtp-user you@gmail.com --smtp-password yourpassword \\
    --email-from you@gmail.com --email-to team@company.com

  # Save JSON report
  python main.py --url https://argocd.example.com --token <token> --output json

  # Exit with non-zero code if drift found (useful for CI)
  python main.py --url https://argocd.example.com --token <token> --fail-on-drift
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from src.detector import scan
from src.reporter import print_report, save_json_report, send_slack_alert, send_email_alert


def parse_args():
    p = argparse.ArgumentParser(
        description="GitOps Drift Detector — scan ArgoCD for drifted applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    # Connection
    p.add_argument("--url",            required=True,  help="ArgoCD server URL")
    p.add_argument("--username",       default="admin",help="ArgoCD username")
    p.add_argument("--password",       default=None,   help="ArgoCD password")
    p.add_argument("--token",          default=None,   help="ArgoCD bearer token (overrides username/password)")
    p.add_argument("--no-verify-ssl",  action="store_true", help="Disable TLS verification")
    p.add_argument("--project",        default=None,   help="Filter by ArgoCD project name")

    # Output
    p.add_argument("--output", choices=["terminal", "json", "both"], default="both",
                   help="Output format (default: both)")
    p.add_argument("--report-dir",     default="reports", help="Directory for JSON reports")

    # Slack
    p.add_argument("--slack-webhook",  default=None,   help="Slack incoming webhook URL")

    # Email
    p.add_argument("--smtp-host",      default=None)
    p.add_argument("--smtp-port",      type=int, default=587)
    p.add_argument("--smtp-user",      default=None)
    p.add_argument("--smtp-password",  default=None)
    p.add_argument("--email-from",     default=None)
    p.add_argument("--email-to",       default=None,   help="Comma-separated recipients")

    # CI mode
    p.add_argument("--fail-on-drift",  action="store_true",
                   help="Exit with code 1 if any drift is detected (useful for CI pipelines)")

    return p.parse_args()


def main():
    args = parse_args()

    if not args.token and not args.password:
        print("  Error: provide --token or --password")
        sys.exit(1)

    print("\n🔍 GitOps Drift Detector")
    print("━" * 40)

    try:
        report = scan(
            argocd_url=args.url,
            username=args.username,
            password=args.password or "",
            token=args.token,
            verify_ssl=not args.no_verify_ssl,
            project_filter=args.project,
        )
    except Exception as e:
        print(f"\n  Error connecting to ArgoCD: {e}")
        sys.exit(1)

    # Terminal output
    if args.output in ("terminal", "both"):
        print_report(report)

    # JSON output
    if args.output in ("json", "both"):
        path = save_json_report(report, output_dir=args.report_dir)
        print(f"  JSON report saved to: {path}\n")

    # Slack
    if args.slack_webhook:
        try:
            send_slack_alert(report, args.slack_webhook)
        except Exception as e:
            print(f"  Slack alert failed: {e}")

    # Email
    if args.smtp_host and args.email_to:
        try:
            send_email_alert(
                report=report,
                smtp_host=args.smtp_host,
                smtp_port=args.smtp_port,
                smtp_user=args.smtp_user,
                smtp_password=args.smtp_password,
                from_addr=args.email_from,
                to_addrs=[a.strip() for a in args.email_to.split(",")],
            )
        except Exception as e:
            print(f"  Email alert failed: {e}")

    # CI exit code
    if args.fail_on_drift and report.summary["drifted"] > 0:
        print(f"  Exiting with code 1 — {report.summary['drifted']} drifted app(s) detected.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
