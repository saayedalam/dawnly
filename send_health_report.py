# send_health_report.py
# Purpose: Send a weekly source health digest to the Dawnly operator.
#
# Fetches source_health.json from the public GitHub Pages URL at runtime,
# builds a formatted HTML email with per-source sparklines and a summary,
# and sends it via the Resend API.
#
# Intended to run every Monday at 7AM EST via GitHub Actions (health_report.yml).
# Requires: RESEND_API_KEY and OPERATOR_EMAIL in environment / GitHub secrets.

import json
import logging
import os
import smtplib
import urllib.request
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

HEALTH_JSON_URL  = "https://saayedalam.github.io/dawnly/source_health.json"

SMTP_HOST        = "smtp.gmail.com"
SMTP_PORT        = 587
SUBJECT_TEMPLATE = "Dawnly Source Health · Week of {date}"

SPARKLINE_CHARS  = " ▁▂▃▄▅▆▇█"
SPARKLINE_DAYS   = 7


# -------------------------------------------------------------------------
# Data fetching
# -------------------------------------------------------------------------

def fetch_health_data() -> dict | None:
    """
    Fetch source_health.json from the public GitHub Pages URL.
    Returns None if the file doesn't exist yet (404) — this is expected
    on first run before the pipeline has produced any health data.
    Raises on other HTTP errors or JSON decode failures.
    """
    logger.info(f"Fetching health data from {HEALTH_JSON_URL}")
    try:
        with urllib.request.urlopen(HEALTH_JSON_URL, timeout=15) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.warning(
                "source_health.json not found (HTTP 404). "
                "The pipeline must run at least once before health data is available. "
                "No email will be sent."
            )
            return None
        raise

    data = json.loads(raw)
    logger.info(
        f"Loaded health data — {data.get('source_count', '?')} sources, "
        f"last updated: {data.get('last_updated', '?')}"
    )
    return data


# -------------------------------------------------------------------------
# Sparkline builder
# -------------------------------------------------------------------------

def build_sparkline(articles: list[int], days: int = SPARKLINE_DAYS) -> str:
    """
    Build a Unicode sparkline string from the last `days` article counts.
    Scales each count to one of 9 block characters (space through █).
    If fewer than `days` entries exist, left-pads with spaces.
    """
    window = articles[-days:] if len(articles) >= days else articles
    if not window:
        return " " * days

    max_val = max(window) if max(window) > 0 else 1
    chars = []
    for val in window:
        idx = round((val / max_val) * (len(SPARKLINE_CHARS) - 1))
        chars.append(SPARKLINE_CHARS[idx])

    # Left-pad with spaces if window is shorter than requested days
    padding = days - len(chars)
    return " " * padding + "".join(chars)


# -------------------------------------------------------------------------
# Per-source stats
# -------------------------------------------------------------------------

def compute_source_stats(entry: dict) -> dict:
    """
    Compute summary stats for a single source from its health log entry.
    Returns a dict with ok_days, error_days, empty_days, avg_articles,
    latest_status, latest_count, and sparkline for the last 7 days.
    """
    dates    = entry.get("dates", [])
    articles = entry.get("articles", [])
    statuses = entry.get("status", [])

    days_tracked  = len(dates)
    ok_days       = statuses.count("ok")
    error_days    = statuses.count("error")
    empty_days    = statuses.count("empty")
    avg_articles  = round(sum(articles) / days_tracked, 1) if days_tracked else 0.0
    latest_status = statuses[-1] if statuses else "unknown"
    latest_count  = articles[-1] if articles else 0
    sparkline     = build_sparkline(articles, SPARKLINE_DAYS)

    return {
        "days_tracked":   days_tracked,
        "ok_days":        ok_days,
        "error_days":     error_days,
        "empty_days":     empty_days,
        "avg_articles":   avg_articles,
        "latest_status":  latest_status,
        "latest_count":   latest_count,
        "sparkline":      sparkline,
    }


# -------------------------------------------------------------------------
# HTML email builder
# -------------------------------------------------------------------------

STATUS_ICON  = {"ok": "✓", "empty": "○", "error": "✗", "unknown": "?"}
STATUS_COLOR = {
    "ok":      "#2d6a4f",   # dark green
    "empty":   "#b5630a",   # amber-warning
    "error":   "#c0392b",   # red
    "unknown": "#888888",
}
ROW_BG = {
    "ok":      "#f9f9f9",
    "empty":   "#fff8f0",
    "error":   "#fff3f3",
    "unknown": "#f5f5f5",
}


def build_html(data: dict) -> str:
    """
    Build the full HTML email body from health data.
    Designed to render correctly in all major email clients —
    uses inline styles, table layout, no JavaScript, no SVG.
    """
    sources_log: dict = data.get("sources", {})
    last_updated: str = data.get("last_updated", "unknown")
    week_of = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Compute stats for all sources
    all_stats = {}
    for name, entry in sources_log.items():
        all_stats[name] = {
            "entry": entry,
            "stats": compute_source_stats(entry),
        }

    # Sort: errors first, then empty, then ok — alpha within each group
    def sort_key(item):
        s = item[1]["stats"]["latest_status"]
        order = {"error": 0, "empty": 1, "ok": 2, "unknown": 3}
        return (order.get(s, 9), item[0].lower())

    sorted_sources = sorted(all_stats.items(), key=sort_key)

    # Summary counts
    total        = len(all_stats)
    ok_count     = sum(1 for _, v in all_stats.items() if v["stats"]["latest_status"] == "ok")
    empty_count  = sum(1 for _, v in all_stats.items() if v["stats"]["latest_status"] == "empty")
    error_count  = sum(1 for _, v in all_stats.items() if v["stats"]["latest_status"] == "error")

    flagged = [
        (name, v) for name, v in sorted_sources
        if v["stats"]["latest_status"] in ("error", "empty")
    ]

    # ── Build source rows ──────────────────────────────────────────────
    rows_html = ""
    for name, v in sorted_sources:
        entry  = v["entry"]
        stats  = v["stats"]
        status = stats["latest_status"]
        icon   = STATUS_ICON.get(status, "?")
        color  = STATUS_COLOR.get(status, "#888")
        bg     = ROW_BG.get(status, "#f9f9f9")
        tier   = entry.get("tier", "—")
        region = entry.get("region", "—")

        # Reliability percentage
        tracked = stats["days_tracked"]
        reliability = f"{round(stats['ok_days'] / tracked * 100)}%" if tracked else "—"

        rows_html += f"""
        <tr style="background:{bg}; border-bottom:1px solid #e8e0cc;">
          <td style="padding:8px 12px; font-family:monospace; font-size:13px;
                     color:{color}; white-space:nowrap;">{icon}</td>
          <td style="padding:8px 12px; font-size:13px; font-weight:500;
                     color:#1a1408;">{name}</td>
          <td style="padding:8px 12px; font-size:11px; color:#9a8a70;
                     white-space:nowrap;">{region}</td>
          <td style="padding:8px 12px; font-size:11px; color:#9a8a70;
                     text-transform:uppercase; letter-spacing:0.5px;">{tier}</td>
          <td style="padding:8px 14px; font-family:monospace; font-size:14px;
                     letter-spacing:2px; color:#5a5040;
                     white-space:nowrap;">{stats['sparkline']}</td>
          <td style="padding:8px 12px; font-size:12px; color:#5a5040;
                     text-align:right; white-space:nowrap;">{stats['avg_articles']}/day</td>
          <td style="padding:8px 12px; font-size:12px; color:#5a5040;
                     text-align:right; white-space:nowrap;">{reliability}</td>
          <td style="padding:8px 12px; font-size:12px; color:{color};
                     text-align:right; white-space:nowrap;">
            {stats['ok_days']}ok · {stats['empty_days']}empty · {stats['error_days']}err
          </td>
        </tr>"""

    # ── Flagged sources callout ────────────────────────────────────────
    flagged_html = ""
    if flagged:
        flagged_items = ""
        for name, v in flagged:
            stats  = v["stats"]
            status = stats["latest_status"]
            color  = STATUS_COLOR.get(status, "#888")
            icon   = STATUS_ICON.get(status, "?")
            flagged_items += f"""
            <tr>
              <td style="padding:6px 12px; font-family:monospace;
                         color:{color};">{icon}</td>
              <td style="padding:6px 12px; font-size:13px;
                         color:#1a1408; font-weight:500;">{name}</td>
              <td style="padding:6px 12px; font-size:12px;
                         color:{color};">{status.upper()}</td>
              <td style="padding:6px 12px; font-size:12px; color:#9a8a70;">
                {stats['ok_days']}d ok / {stats['error_days']}d err / {stats['empty_days']}d empty
              </td>
            </tr>"""

        flagged_html = f"""
        <div style="margin:0 0 28px 0; padding:18px 20px;
                    background:#fff8f0; border-left:3px solid #c8820a;">
          <div style="font-family:'Jost',sans-serif; font-size:9px;
                      font-weight:500; letter-spacing:3px;
                      text-transform:uppercase; color:#9a8a70;
                      margin-bottom:12px;">Needs Attention</div>
          <table width="100%" cellpadding="0" cellspacing="0">
            {flagged_items}
          </table>
        </div>"""

    # ── Full HTML ──────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Dawnly Source Health · {week_of}</title>
</head>
<body style="margin:0; padding:0; background:#f5f0e4;
             font-family:Georgia, serif; color:#1a1408;">

  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#f5f0e4; padding:40px 20px;">
    <tr><td>
      <table width="640" align="center" cellpadding="0" cellspacing="0"
             style="background:#f5f0e4; max-width:640px; margin:0 auto;">

        <!-- Header -->
        <tr>
          <td style="padding:0 0 28px 0; border-bottom:3px double rgba(42,36,16,0.3);">
            <div style="font-family:Georgia,serif; font-size:32px; font-weight:700;
                        color:#1a1408; letter-spacing:2px;">Dawnly</div>
            <div style="font-family:Arial,sans-serif; font-size:9px; font-weight:500;
                        letter-spacing:4px; text-transform:uppercase;
                        color:#9a8a70; margin-top:4px;">Source Health Report</div>
            <div style="font-family:Arial,sans-serif; font-size:11px;
                        color:#9a8a70; margin-top:8px;">Week of {week_of}</div>
          </td>
        </tr>

        <!-- Summary bar -->
        <tr>
          <td style="padding:24px 0 20px 0;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#ede6d4; border:1px solid rgba(42,36,16,0.15);">
              <tr>
                <td style="padding:18px 20px; text-align:center; width:25%;">
                  <div style="font-family:Georgia,serif; font-size:36px;
                               font-weight:700; color:#1a1408; line-height:1;">{total}</div>
                  <div style="font-family:Arial,sans-serif; font-size:8px;
                               letter-spacing:2px; text-transform:uppercase;
                               color:#9a8a70; margin-top:4px;">Sources</div>
                </td>
                <td style="padding:18px 20px; text-align:center; width:25%;
                            border-left:1px solid rgba(42,36,16,0.15);">
                  <div style="font-family:Georgia,serif; font-size:36px;
                               font-weight:700; color:#2d6a4f; line-height:1;">{ok_count}</div>
                  <div style="font-family:Arial,sans-serif; font-size:8px;
                               letter-spacing:2px; text-transform:uppercase;
                               color:#9a8a70; margin-top:4px;">Healthy</div>
                </td>
                <td style="padding:18px 20px; text-align:center; width:25%;
                            border-left:1px solid rgba(42,36,16,0.15);">
                  <div style="font-family:Georgia,serif; font-size:36px;
                               font-weight:700; color:#b5630a; line-height:1;">{empty_count}</div>
                  <div style="font-family:Arial,sans-serif; font-size:8px;
                               letter-spacing:2px; text-transform:uppercase;
                               color:#9a8a70; margin-top:4px;">Empty</div>
                </td>
                <td style="padding:18px 20px; text-align:center; width:25%;
                            border-left:1px solid rgba(42,36,16,0.15);">
                  <div style="font-family:Georgia,serif; font-size:36px;
                               font-weight:700; color:#c0392b; line-height:1;">{error_count}</div>
                  <div style="font-family:Arial,sans-serif; font-size:8px;
                               letter-spacing:2px; text-transform:uppercase;
                               color:#9a8a70; margin-top:4px;">Errors</div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Flagged sources -->
        <tr><td>{flagged_html}</td></tr>

        <!-- Section label -->
        <tr>
          <td style="padding:0 0 12px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="border-top:1px solid rgba(42,36,16,0.15);"></td>
                <td style="padding:0 12px; font-family:Arial,sans-serif;
                            font-size:8px; font-weight:500; letter-spacing:3px;
                            text-transform:uppercase; color:#9a8a70;
                            white-space:nowrap;">All Sources</td>
                <td style="border-top:1px solid rgba(42,36,16,0.15);"></td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Sparkline legend -->
        <tr>
          <td style="padding:0 0 8px 0;">
            <div style="font-family:Arial,sans-serif; font-size:10px;
                        color:#9a8a70; text-align:right;">
              Sparkline = last 7 days article count &nbsp;·&nbsp;
              ▁ low &nbsp;█ high
            </div>
          </td>
        </tr>

        <!-- Source table -->
        <tr>
          <td style="padding:0 0 32px 0;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border:1px solid rgba(42,36,16,0.15);
                           border-collapse:collapse;">
              <!-- Column headers -->
              <tr style="background:#e4dcc8; border-bottom:2px solid rgba(42,36,16,0.2);">
                <td style="padding:8px 12px; font-family:Arial,sans-serif;
                            font-size:8px; letter-spacing:2px;
                            text-transform:uppercase; color:#9a8a70;"> </td>
                <td style="padding:8px 12px; font-family:Arial,sans-serif;
                            font-size:8px; letter-spacing:2px;
                            text-transform:uppercase; color:#9a8a70;">Source</td>
                <td style="padding:8px 12px; font-family:Arial,sans-serif;
                            font-size:8px; letter-spacing:2px;
                            text-transform:uppercase; color:#9a8a70;">Region</td>
                <td style="padding:8px 12px; font-family:Arial,sans-serif;
                            font-size:8px; letter-spacing:2px;
                            text-transform:uppercase; color:#9a8a70;">Tier</td>
                <td style="padding:8px 14px; font-family:Arial,sans-serif;
                            font-size:8px; letter-spacing:2px;
                            text-transform:uppercase; color:#9a8a70;">7d Trend</td>
                <td style="padding:8px 12px; font-family:Arial,sans-serif;
                            font-size:8px; letter-spacing:2px;
                            text-transform:uppercase; color:#9a8a70;
                            text-align:right;">Avg</td>
                <td style="padding:8px 12px; font-family:Arial,sans-serif;
                            font-size:8px; letter-spacing:2px;
                            text-transform:uppercase; color:#9a8a70;
                            text-align:right;">Reliability</td>
                <td style="padding:8px 12px; font-family:Arial,sans-serif;
                            font-size:8px; letter-spacing:2px;
                            text-transform:uppercase; color:#9a8a70;
                            text-align:right;">History</td>
              </tr>
              {rows_html}
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 0 0 0; border-top:1px solid rgba(42,36,16,0.15);">
            <div style="font-family:Arial,sans-serif; font-size:9px;
                        letter-spacing:2px; text-transform:uppercase;
                        color:#9a8a70; text-align:center;">
              Dawnly Pipeline · Last updated {last_updated[:10]} ·
              Data from source_health.json
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>

</body>
</html>"""


# -------------------------------------------------------------------------
# Email sender
# -------------------------------------------------------------------------

def send_email(html: str, subject: str) -> None:
    """
    Send the health report email via Gmail SMTP using an App Password.
    Reads GMAIL_ADDRESS and GMAIL_APP_PASSWORD from environment variables.
    Sends from and to the same Gmail address (operator's own inbox).

    To set up a Gmail App Password:
      Google Account → Security → 2-Step Verification → App Passwords
    """
    gmail_address  = os.environ.get("GMAIL_ADDRESS", "").strip()
    app_password   = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    operator_email = os.environ.get("OPERATOR_EMAIL", gmail_address).strip()

    if not gmail_address:
        raise ValueError("GMAIL_ADDRESS environment variable is not set")
    if not app_password:
        raise ValueError("GMAIL_APP_PASSWORD environment variable is not set")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Dawnly Pipeline <{gmail_address}>"
    msg["To"]      = operator_email

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, operator_email, msg.as_string())

    logger.info(f"Email sent to {operator_email} via Gmail SMTP")


# -------------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------------

def main() -> None:
    """Fetch health data, build HTML report, and send via Resend."""
    week_of = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = SUBJECT_TEMPLATE.format(date=week_of)

    logger.info("=" * 55)
    logger.info("DAWNLY HEALTH REPORT")
    logger.info(f"Week of: {week_of}")
    logger.info("=" * 55)

    data = fetch_health_data()
    if data is None:
        logger.info("No health data available yet — skipping email. Run the pipeline first.")
        return

    html = build_html(data)
    send_email(html, subject)

    logger.info("Health report sent.")


if __name__ == "__main__":
    main()
