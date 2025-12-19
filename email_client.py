# email_client.py

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from config import (
    EMAIL_FROM,
    EMAIL_PASSWORD,
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_USERNAME,
)

# ----------------------------
# Brand styling (Jersey Mike's)
# ----------------------------
BRAND_RED = "#EE3227"   # Permanent Geranium Lake
BRAND_BLUE = "#134A7C"  # Dark Cerulean
BRAND_NAME = "Jersey Mike’s"

DOWNLOAD_BASE = "https://jerseymikespowerplay.com/download"

# Inline (CID) logo config
LOGO_CID = "jerseymikeslogo"

# Project-root-ish: email_client.py is typically in root; adjust if yours is in /src
LOGO_LOCAL_PATH = Path(__file__).resolve().parent / "assets" / "overlays" / "jersey_logo.png"


def _format_name(first_name: str) -> str:
    """Formats the name to Title Case or returns 'Player' if empty."""
    name = (first_name or "").strip()
    if not name:
        return "Player"
    # Title-case each word
    return " ".join([w[:1].upper() + w[1:].lower() for w in name.split()])


def _download_link_for_email(user_email: str) -> str:
    """
    Builds: https://jerseymikespowerplay.com/download/<encoded-email>
    URL-encodes the email so special characters don't break the path.
    """
    return f"{DOWNLOAD_BASE}/{quote((user_email or '').strip(), safe='')}"


def _build_email_html(
    first_name: str,
    user_email: str,
) -> str:
    """Generates the HTML body of the email with brand styling."""
    safe_name = _format_name(first_name)
    download_url = _download_link_for_email(user_email)

    # CID embedded logo in a white tile to avoid “transparent edges” looking bad
    logo_tile = f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="background:#ffffff; border-radius:16px; padding:6px; border:1px solid #e5e7eb;">
          <img src="cid:{LOGO_CID}" alt="{BRAND_NAME}" width="54" height="54"
               style="display:block; border-radius:12px;" />
        </td>
      </tr>
    </table>
    """

    html = f"""
    <html>
    <body style="margin:0; padding:0; background:#f3f4f6;
                 font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6; padding:24px 0;">
        <tr>
          <td align="center">

            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="max-width:640px; background:#ffffff; border-radius:18px; overflow:hidden;
                          box-shadow:0 10px 28px rgba(0,0,0,0.10);">

              <tr>
                <td style="padding:0;">
                  <div style="height:7px; background:{BRAND_BLUE};"></div>
                  <div style="height:7px; background:{BRAND_RED};"></div>
                </td>
              </tr>

              <tr>
                <td style="padding:30px 30px 26px 30px;">

                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td valign="middle">
                        <div style="font-size:22px; font-weight:950; color:{BRAND_BLUE}; line-height:1.15;">
                          Your Hero is Ready
                        </div>
                        <div style="margin-top:6px; font-size:13px; color:#6b7280; line-height:1.45;">
                          Open your download page to view and save your results.
                        </div>
                      </td>
                      <td valign="middle" align="right" style="width:86px;">
                        {logo_tile}
                      </td>
                    </tr>
                  </table>

                  <div style="height:18px;"></div>

                  <div style="font-size:15px; color:#111827; line-height:1.6;">
                    Hi <strong>{safe_name}</strong>,<br/>
                    Thanks for visiting our hockey kiosk! Your content is ready.
                  </div>

                  <div style="height:16px;"></div>
                  <div style="padding:16px; border:1px solid #e5e7eb; border-radius:16px; background:#fbfbfd;">
                    <div style="height:4px; background:{BRAND_BLUE}; border-radius:999px;"></div>
                    <div style="height:12px;"></div>

                    <div style="font-size:14px; font-weight:900; color:{BRAND_BLUE}; margin-bottom:10px;">
                      Download Your Results
                    </div>

                    <a href="{download_url}"
                       style="display:inline-block; padding:14px 18px; background:{BRAND_BLUE}; color:#ffffff;
                              border-radius:12px; text-decoration:none; font-weight:900; font-size:14px;">
                      Open Download Page
                    </a>

                    <div style="margin-top:12px; font-size:12px; color:#6b7280; line-height:1.45;">
                      If the page doesn’t open, copy and paste this link into your browser:
                      <span style="word-break:break-all; color:#111827;">{download_url}</span>
                    </div>
                  </div>

                  <div style="height:24px;"></div>
                  <div style="height:1px; background:#e5e7eb;"></div>

                  <div style="height:14px;"></div>
                  <div style="height:5px; background:{BRAND_BLUE}; border-radius:999px;"></div>
                  <div style="height:6px;"></div>
                  <div style="height:5px; background:{BRAND_RED}; border-radius:999px;"></div>
                  <div style="height:16px;"></div>

                  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr>
                      <td valign="top" style="width:78px; padding-right:14px;">
                        {logo_tile}
                      </td>
                      <td valign="top" style="color:#111827;">
                        <div style="font-size:15px; font-weight:950; color:{BRAND_BLUE}; line-height:1.2;">
                          {BRAND_NAME}
                        </div>
                        <div style="font-size:12.5px; font-weight:800; color:#374151; margin-top:3px;">
                          Hockey Kiosk — Player Content Delivery
                        </div>
                        <div style="margin-top:10px; font-size:12.5px; color:#4b5563; line-height:1.55;">
                          Automated message from the Jersey Mike’s event experience.
                        </div>
                        <div style="margin-top:12px; font-size:11px; color:#9ca3af; line-height:1.45;">
                          If you didn’t request this email, you can safely ignore it.
                        </div>
                      </td>
                    </tr>
                  </table>

                </td>
              </tr>
            </table>

            <div style="height:14px;"></div>

            <div style="max-width:640px; padding:0 10px; font-size:11px; color:#9ca3af; line-height:1.4; text-align:center;">
              © {BRAND_NAME}. Automated message.
            </div>

          </td>
        </tr>
      </table>

    </body>
    </html>
    """
    return html


def send_player_result_email(
    to_email: str,
    first_name: str,
    card_url: str = "",      # kept for compatibility with existing calls
    video_url: Optional[str] = None,  # kept for compatibility
) -> None:
    """
    Sends a single-button email to the user's download page.
    """
    if not (EMAIL_USERNAME and EMAIL_PASSWORD):
        raise RuntimeError("Email credentials not configured (EMAIL_USERNAME / EMAIL_PASSWORD)")

    safe_name = _format_name(first_name)
    download_url = _download_link_for_email(to_email)

    subject = "Your Jersey Mike’s Hero is Ready!"

    plain_text = (
        f"Hi {safe_name},\n\n"
        f"Your Jersey Mike’s hero content is ready.\n"
        f"Open your download page:\n{download_url}\n\n"
        "If you didn’t request this email, you can ignore it.\n"
    )

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    
    # 1. Set the initial text content
    msg.set_content(plain_text)

    # 2. Add HTML as an alternative.
    # This modifies msg and returns None.
    msg.add_alternative(
        _build_email_html(first_name=first_name, user_email=to_email),
        subtype="html",
    )

    # 3. Retrieve the HTML part from the message payload to add related items.
    # The payload is now [PlainTextPart, HTMLPart].
    html_part = msg.get_payload()[1]

    # 4. Attach inline logo (CID) using the correct PNG subtype.
    logo_bytes = LOGO_LOCAL_PATH.read_bytes()
    html_part.add_related(
        logo_bytes,
        maintype="image",
        subtype="png",  # Updated from jpeg to match .png extension
        cid=f"<{LOGO_CID}>",
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"[email_client] Sent result email to {to_email}")
