# 🔍 gitops-drift-detector

> Scan your ArgoCD applications for config drift and deliver alerts to Slack and email — from the CLI or as a scheduled CI pipeline.

Built from real-world experience operating GitOps platforms across 10+ business units at DXC Technology.

---

## What it does

- Connects to any ArgoCD instance using username/password or a bearer token
- Scans every application for sync and health status
- Detects drift: OutOfSync, Degraded, Missing, or Unknown applications
- Sends colour-coded alerts to **Slack** and/or **email**
- Outputs a **terminal report** and a **JSON file** for downstream processing
- Supports **CI/CD mode** — exits with code 1 if drift is found, blocking pipelines

---

## Sample terminal output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🔍  GitOps Drift Detector
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ArgoCD   : https://argocd.example.com
  Scanned  : 2026-05-25 09:42 UTC
  Total    : 12 applications

  SUMMARY
  Total apps    : 12
  Healthy       : 9
  Drifted       : 3
  Drift rate    : 25.0%

  DRIFTED APPLICATIONS
  ─────────────────────────────────────────────────────────────────

  payments-api  [production]
  Sync    : ⚠️  OutOfSync
  Health  : ✅  Healthy
  Repo    : https://github.com/org/platform@main
  ⚠  app is out of sync with Git source
```

---

## Quick start

```bash
pip install -r requirements.txt
```

### Scan with username and password
```bash
python main.py --url https://argocd.example.com --username admin --password secret
```

### Scan with bearer token
```bash
python main.py --url https://argocd.example.com --token <argocd-token>
```

### Send Slack alert
```bash
python main.py --url https://argocd.example.com --token <token> \
  --slack-webhook https://hooks.slack.com/services/xxx/yyy/zzz
```

### Send email alert
```bash
python main.py --url https://argocd.example.com --token <token> \
  --smtp-host smtp.gmail.com --smtp-port 587 \
  --smtp-user you@gmail.com --smtp-password yourpassword \
  --email-from you@gmail.com --email-to team@company.com
```

### Save JSON report only
```bash
python main.py --url https://argocd.example.com --token <token> --output json
```

### CI mode — fail pipeline on drift
```bash
python main.py --url https://argocd.example.com --token <token> --fail-on-drift
```

---

## All options

| Flag | Description |
|---|---|
| `--url` | ArgoCD server URL (required) |
| `--username` | ArgoCD username (default: admin) |
| `--password` | ArgoCD password |
| `--token` | Bearer token (overrides username/password) |
| `--no-verify-ssl` | Disable TLS verification (self-signed certs) |
| `--project` | Filter scan to a specific ArgoCD project |
| `--output` | `terminal`, `json`, or `both` (default: both) |
| `--report-dir` | Directory to save JSON reports (default: reports/) |
| `--slack-webhook` | Slack incoming webhook URL |
| `--smtp-host` | SMTP host for email alerts |
| `--smtp-port` | SMTP port (default: 587) |
| `--smtp-user` | SMTP username |
| `--smtp-password` | SMTP password |
| `--email-from` | Sender email address |
| `--email-to` | Comma-separated recipient addresses |
| `--fail-on-drift` | Exit code 1 if drift found (CI use) |

---

## GitHub Actions — scheduled drift scanning

Add to your repo and configure these secrets: `ARGOCD_URL`, `ARGOCD_TOKEN`, `SLACK_WEBHOOK`.

The included workflow (`.github/workflows/drift-check.yml`) runs every 6 hours and uploads drift reports as artifacts.

```yaml
- name: Run drift scan
  run: |
    python main.py \
      --url "$ARGOCD_URL" \
      --token "$ARGOCD_TOKEN" \
      --slack-webhook "$SLACK_WEBHOOK" \
      --output both \
      --fail-on-drift
```

---

## What gets flagged

| Condition | Meaning |
|---|---|
| `OutOfSync` | App has drifted from its Git source |
| `Degraded` | One or more resources are failing |
| `Missing` | Resources expected by ArgoCD are absent from the cluster |
| `Unknown` | ArgoCD has lost contact with the app or cluster |

---

## Real-world context

At DXC Technology, this type of drift detection was part of the observability platform built for Platform X, which served 10+ business units running production workloads on EKS. Catching drift early — before it causes an incident — was the difference between a 5-minute fix and a 3am page.

---

## Project structure

```
gitops-drift-detector/
├── main.py                          # CLI entrypoint
├── requirements.txt
├── src/
│   ├── detector.py                  # ArgoCD connection and drift analysis
│   └── reporter.py                  # Terminal, JSON, Slack, email output
├── reports/                         # Generated JSON reports saved here
└── .github/workflows/
    └── drift-check.yml              # Scheduled GitHub Actions workflow
```

---

## Requirements

- Python 3.8+
- ArgoCD instance accessible via HTTPS
- ArgoCD token with read access to applications

---

## License

MIT
