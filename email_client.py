# email_client.py

import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from config import (
    EMAIL_FROM,
    EMAIL_PASSWORD,
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_USERNAME,
)


def _build_email_html(
    first_name: str,
    card_url: str,
    video_url: Optional[str],
) -> str:
    """
    Build a nice HTML email body with buttons for card + optional video.
    """
    safe_name = first_name or "Player"

    video_block = ""
    if video_url:
        video_block = f"""
        <tr>
          <td>
            <div style="margin-top: 18px;">
              <div style="font-weight: 600; margin-bottom: 6px;">🎥 Your Highlight Video</div>
              <a href="{video_url}"
                 style="display:inline-block; padding:10px 16px; background:#6C5CE7; color:white;
                        border-radius:8px; text-decoration:none; font-weight:600;">
                  Watch Video
              </a>
              <p style="font-size:13px; color:#777; margin-top:6px;">
                On iPhone: open the link → tap and hold the video → “Save Video”.
              </p>
            </div>
          </td>
        </tr>
        """

    html = f"""
    <html>
    <body style="margin:0; padding:0; background:#f4f6fb;
                 font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">

      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f4f6fb; padding:20px 0;">
        <tr>
          <td align="center">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="max-width:600px; background:#ffffff;
                          border-radius:14px; padding:30px;
                          box-shadow:0 4px 12px rgba(0,0,0,0.08);">

              <!-- Header -->
              <tr>
                <td align="center" style="padding-bottom:10px;">
                  <h1 style="margin:0; font-size:26px; color:#1B1B1B;">
                    Your AI Hockey Hero is Ready! 🏒🔥
                  </h1>
                </td>
              </tr>

              <!-- Greeting -->
              <tr>
                <td style="font-size:16px; color:#333; padding-bottom:18px;">
                  Hi <strong>{safe_name}</strong>,<br>
                  Thanks for visiting our hockey kiosk! Here’s your personalized hero card
                  and highlight video.
                </td>
              </tr>

              <!-- Card section -->
              <tr>
                <td>
                  <div style="font-weight:600; margin-bottom:6px;">🃏 Your Hero Card</div>
                  <a href="{card_url}"
                     style="display:inline-block; padding:10px 16px; background:#0984e3; color:white;
                            border-radius:8px; text-decoration:none; font-weight:600;">
                    View Card
                  </a>
                  <p style="font-size:13px; color:#777; margin-top:6px;">
                    On iPhone: open the link → tap and hold the image → “Save to Photos”.
                  </p>
                </td>
              </tr>

              {video_block}

              <!-- Footer -->
              <tr>
                <td style="padding-top:28px; font-size:13px; color:#999; text-align:center;">
                  Powered by our AI Hockey Experience Engine.<br>
                  If you didn’t request this, you can ignore this email.
                </td>
              </tr>

            </table>
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
    card_url: str,
    video_url: Optional[str] = None,
) -> None:
    """
    Send an email with links to the player's hero card and optional video.

    Raises an exception if credentials are missing or SMTP fails.
    """

    if not (EMAIL_USERNAME and EMAIL_PASSWORD):
        raise RuntimeError(
            "Email credentials not configured (EMAIL_USERNAME / EMAIL_PASSWORD)"
        )

    subject = "Your AI Hockey Hero is Ready!"
    plain_text = (
        f"Hi {first_name or 'Player'},\n\n"
        f"Your AI hockey hero is ready.\n\n"
        f"Hero card: {card_url}\n"
    )
    if video_url:
        plain_text += f"Highlight video: {video_url}\n\n"
    plain_text += (
        "Open these links to view or download your content.\n\n"
        "If you didn't request this email, you can ignore it.\n"
    )

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(plain_text)
    msg.add_alternative(
        _build_email_html(
            first_name=first_name or "Player", card_url=card_url, video_url=video_url
        ),
        subtype="html",
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"[email_client] Sent result email to {to_email}")
