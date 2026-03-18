# send_newsletter.py
# Purpose: Build and send the daily Dawnly newsletter via Buttondown API.
# Reads top10.json, generates a minimal HTML email in Dawnly's style,
# and posts it directly to subscribers.
#
# Called by the newsletter GitHub Actions workflow after the pipeline runs.

import json
import logging
import os
import sys
from datetime import datetime, timezone

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

BUTTONDOWN_API_URL = "https://api.buttondown.com/v1/emails"
TOP10_FILE         = "top10.json"
ROMAN              = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

TAGLINES = [
    "The Morning Paper, Rebuilt For Today",
    "Once A Day. Just Like It Used To Be.",
    "Your Daily Paper. Nothing In Between.",
    "The News, The Way It Used To Feel.",
    "One Edition. Every Morning.",
    "Read It. Put It Down. Live Your Day.",
    "The Paper Lands Once.",
]

# Top headline used as email preview text (shown after subject in inbox)
# Different from subject so inbox doesn't show duplicate content
PREVIEW_INTROS = [
    "Today's ten stories, gathered from around the world.",
    "Your morning briefing. Read it once. Put it down.",
    "Ten stories. One edition. Nothing in between.",
    "The world in ten headlines, ranked by reach.",
    "Algorithmically ranked. Editorially calm.",
    "Global news, distilled. One edition at dawn.",
    "Today's edition is ready.",
]


# -------------------------------------------------------------------------
# Email builder
# -------------------------------------------------------------------------

def build_subject(edition: int, published_at: str) -> str:
    '''
    Build the email subject line.
    Format: Dawnly · Edition N · Month D
    Kept minimal — just brand, edition number, and date.
    The tagline lives inside the email body header instead.
    '''
    try:
        dt       = datetime.fromisoformat(published_at)
        date_str = dt.strftime("%B %-d")
    except Exception:
        date_str = datetime.now(timezone.utc).strftime("%B %-d")

    return f"Dawnly · Edition {edition} · {date_str}"


def build_html(stories: list[dict], edition: int, published_at: str) -> str:
    '''
    Build a minimal HTML email body in Dawnly's newspaper style.

    Key layout decisions:
    - Outer wrapper: full-width table, 16px side padding on mobile
    - Inner content: max-width 600px, fluid width 100%
    - Story padding: 4% each side (fluid) instead of fixed 40px
      so it scales gracefully on mobile
    - Headline font: 18px (down from 20px) for better mobile wrapping
    - Preview text: hidden span shown only to email clients as inbox preview
    '''
    # Format the date for the email header
    try:
        dt = datetime.fromisoformat(published_at)
        date_str    = dt.strftime("%A, %B %-d, %Y").upper()
        day_of_year = dt.timetuple().tm_yday
    except Exception:
        dt          = datetime.now(timezone.utc)
        date_str    = dt.strftime("%A, %B %-d, %Y").upper()
        day_of_year = dt.timetuple().tm_yday

    tagline = TAGLINES[day_of_year % len(TAGLINES)]

    # Preview text — shown in inbox after subject, before opening email
    # Prevents email clients from pulling the first visible text (which would
    # duplicate the header date/edition info)
    preview_text = PREVIEW_INTROS[day_of_year % len(PREVIEW_INTROS)]

    # Build each story row
    rows_html = ""
    for i, story in enumerate(stories):
        rank    = ROMAN[i] if i < len(ROMAN) else str(i + 1)
        regions = ", ".join(story.get("regions", []))
        sources = story.get("sources", [])

        top_link     = sources[0]["link"] if sources else "#"
        headline     = story.get("headline", "")
        source_names = " · ".join(s["name"] for s in sources[:3])

        # Last row has no border-bottom
        border = "border-bottom: 1px solid #e8e0cc;" if i < len(stories) - 1 else ""

        rows_html += f"""
        <tr>
          <td style="padding: 14px 0; {border}">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="width: 24px; vertical-align: top; padding-top: 3px;">
                  <span style="font-family: 'Jost', sans-serif; font-size: 9px;
                               font-weight: 500; letter-spacing: 2px; color: #9a8a70;
                               text-transform: uppercase;">{rank}</span>
                </td>
                <td style="vertical-align: top;">
                  <a href="{top_link}"
                     style="font-family: 'Cormorant Garamond', Georgia, serif;
                            font-size: 18px; font-weight: 700; color: #1a1408;
                            line-height: 1.3; text-decoration: none;
                            display: block; margin-bottom: 5px;">{headline}</a>
                  <span style="font-family: 'Jost', sans-serif; font-size: 8px;
                               font-weight: 400; letter-spacing: 1.5px; color: #9a8a70;
                               text-transform: uppercase;">{source_names}</span>
                  {f'<br><span style="font-family: Jost, sans-serif; font-size: 8px; font-weight: 400; letter-spacing: 1px; color: #b8a888; text-transform: uppercase;">{regions}</span>' if regions else ''}
                </td>
              </tr>
            </table>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;700&family=Jost:wght@300;400;500&display=swap"
        rel="stylesheet"/>
</head>
<body style="margin: 0; padding: 0; background: #f5f0e4;
             font-family: 'Cormorant Garamond', Georgia, serif;">

  <!--
    Preview text — hidden from visible email body.
    Email clients (Gmail, Apple Mail, Outlook) show this text
    in the inbox after the subject line. Without it, they grab
    the first visible text — which would repeat the header info.
  -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">
    {preview_text}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;
  </div>

  <table width="100%" cellpadding="0" cellspacing="0"
         style="background: #f5f0e4;">
    <tr>
      <td>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background: #f5f0e4;">

          <!-- Section rule -->
          <tr>
            <td style="padding: 10px 0 0;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="border-top: 1px solid rgba(42,36,16,0.2);"></td>
                  <td style="padding: 0 10px; white-space: nowrap;
                              font-family: 'Jost', sans-serif; font-size: 8px;
                              font-weight: 500; letter-spacing: 3px; color: #1a1408;
                              text-transform: uppercase;">
                    Today's Ten Stories
                  </td>
                  <td style="border-top: 1px solid rgba(42,36,16,0.2);"></td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Stories — fluid 5% padding scales on mobile -->
          <tr>
            <td>
              <table width="100%" cellpadding="0" cellspacing="0">
                {rows_html}
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 16px 0 24px;
                       border-top: 1px solid rgba(42,36,16,0.15);">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="font-family: 'Jost', sans-serif; font-size: 8px;
                                 font-weight: 400; letter-spacing: 2px; color: #9a8a70;
                                 text-transform: uppercase;">
                      Algorithmically Ranked · 10 Stories · Resets 6AM EST
                    </span>
                  </td>
                  <td align="right">
                    <a href="https://saayedalam.me/dawnly"
                       style="font-family: 'Jost', sans-serif; font-size: 8px;
                              font-weight: 500; letter-spacing: 2px; color: #c8820a;
                              text-transform: uppercase; text-decoration: none;">
                      Dawnly.News →
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


# -------------------------------------------------------------------------
# Buttondown sender
# -------------------------------------------------------------------------

def send_email(subject: str, body: str, api_key: str) -> None:
    '''
    POST the email to Buttondown's API with status=about_to_send.
    Uses API version 2026-01-01 for stable send-on-POST behaviour.
    Raises on any non-2xx response.
    '''
    headers = {
        "Authorization":  f"Token {api_key}",
        "Content-Type":   "application/json",
        "X-API-Version":  "2026-01-01",
    }
    payload = {
        "subject": subject,
        "body":    body,
        "status":  "about_to_send",
    }

    logger.info("Sending email via Buttondown API...")
    response = requests.post(BUTTONDOWN_API_URL, headers=headers, json=payload, timeout=30)

    if not response.ok:
        logger.error(f"Buttondown API error {response.status_code}: {response.text}")
        response.raise_for_status()

    logger.info(f"Email queued successfully — status {response.status_code}")


# -------------------------------------------------------------------------
# Main
# -------------------------------------------------------------------------

def main() -> None:
    api_key = os.environ.get("BUTTONDOWN_API_KEY")
    if not api_key:
        logger.error("BUTTONDOWN_API_KEY environment variable not set")
        sys.exit(1)

    if not os.path.exists(TOP10_FILE):
        logger.error(f"{TOP10_FILE} not found — pipeline may not have run yet")
        sys.exit(1)

    with open(TOP10_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    stories      = data.get("stories", [])
    published_at = data.get("published_at", "")

    if not stories:
        logger.error("No stories found in top10.json — aborting newsletter send")
        sys.exit(1)

    logger.info(f"Loaded {len(stories)} stories from {TOP10_FILE}")

    try:
        launch    = datetime(2026, 3, 12, tzinfo=timezone.utc)
        pub_dt    = datetime.fromisoformat(published_at)
        edition   = max(1, (pub_dt.date() - launch.date()).days + 1)
    except Exception:
        edition = 1

    subject = build_subject(edition, published_at)
    body    = build_html(stories, edition, published_at)

    logger.info(f"Subject: {subject}")
    send_email(subject, body, api_key)

    logger.info("Newsletter send complete")


if __name__ == "__main__":
    main()
