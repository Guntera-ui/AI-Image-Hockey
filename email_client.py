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

# ----------------------------
# Brand styling (Jersey Mike's)
# ----------------------------
BRAND_RED = "#EE3227"   # Permanent Geranium Lake
BRAND_BLUE = "#134A7C"  # Dark Cerulean

BRAND_NAME = "Jersey Mike’s"
LOGO_URL = "https://firebasestorage.googleapis.com/v0/b/ai-image-app-e900c.firebasestorage.app/o/assets%2Fjersey_Mikes.jpg?alt=media&token=b6bb52c0-15fd-4f16-a65d-26c7a588d895"
BRAND_WEBSITE = "https://www.jerseymikes.com/"


def _format_name(first_name: str) -> str:
    name = (first_name or "").strip()
    if not name:
        return "Player"
    return " ".join(w[:1].upper() + w[1:].lower() for w in name.split())


def _brand_logo_tile(size_px: int = 54) -> str:
    return f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="background:#ffffff; border-radius:16px; padding:6px; border:1px solid #e5e7eb;">
          <img src="{LOGO_URL}" alt="{BRAND_NAME}" width="{size_px}" height="{size_px}"
               style="display:block; border-radius:12px;" />
        </td>
      </tr>
    </table>
    """


def _build_email_html(first_name: str, card_url: str, video_url: Optional[str]) -> str:
    safe_name = _format_name(first_name)

    # ---- stacked content card ----
    video_section = ""
    if video_url:
        video_section = f"""
        <!-- Divider -->
        <tr>
          <td style="padding:0 16px;">
            <div style="height:1px; background:#e5e7eb;"></div>
          </td>
        </tr>

        <!-- Video section -->
        <tr>
          <td style="padding:16px;">
            <div style="height:4px; background:{BRAND_RED}; border-radius:999px;"></div>
            <div style="height:12px;"></div>

            <div style="font-size:14px; font-weight:900; color:{BRAND_BLUE}; margin-bottom:10px;">
              Your Highlight Video
            </div>

            <a href="{video_url}"
               style="display:inline-block; padding:12px 16px; background:{BRAND_RED}; color:#ffffff;
                      border-radius:12px; text-decoration:none; font-weight:900; font-size:14px;">
              Watch Video
            </a>
          </td>
        </tr>
        """

    stacked_content_card = f"""
    <!-- Stacked content card -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb; border-radius:18px; background:#fbfbfd; overflow:hidden;">

      <!-- Hero card section -->
      <tr>
        <td style="padding:16px;">
          <div style="height:4px; background:{BRAND_BLUE}; border-radius:999px;"></div>
          <div style="height:12px;"></div>

          <div style="font-size:14px; font-weight:900; color:{BRAND_BLUE}; margin-bottom:10px;">
            Your Hero Card
          </div>

          <a href="{card_url}"
             style="display:inline-block; padding:12px 16px; background:{BRAND_BLUE}; color:#ffffff;
                    border-radius:12px; text-decoration:none; font-weight:900; font-size:14px;">
            View Card
          </a>
        </td>
      </tr>

      {video_section}

    </table>
    """

    signature = f"""
    <!-- Signature -->
    <tr>
      <td style="padding-top:26px;">
        <div style="height:1px; background:#e5e7eb;"></div>

        <div style="height:14px;"></div>

        <div style="height:5px; background:{BRAND_BLUE}; border-radius:999px;"></div>
        <div style="height:6px;"></div>
        <div style="height:5px; background:{BRAND_RED}; border-radius:999px;"></div>

        <div style="height:16px;"></div>

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td valign="top" style="width:78px; padding-right:14px;">
              {_brand_logo_tile(56)}
            </td>

            <td valign="top"
                style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; color:#111827;">

              <div style="font-size:15px; font-weight:950; color:{BRAND_BLUE}; line-height:1.2;">
                {BRAND_NAME}
              </div>

              <div style="font-size:12.5px; font-weight:800; color:#374151; margin-top:3px;">
                Hockey Kiosk — Player Content Delivery
              </div>

              <div style="margin-top:10px; font-size:12.5px; color:#4b5563; line-height:1.55;">
                Automated message from the Jersey Mike’s event experience.
              </div>

              <div style="margin-top:12px;">
                <a href="{BRAND_WEBSITE}"
                   style="display:inline-block; font-size:12px; font-weight:900; text-decoration:none;
                          color:#ffffff; background:{BRAND_BLUE}; padding:10px 12px; border-radius:10px;">
                  Visit Jersey Mike’s
                </a>
              </div>

              <div style="margin-top:12px; font-size:11px; color:#9ca3af; line-height:1.45;">
                If you didn’t request this email, you can safely ignore it.
              </div>

            </td>
          </tr>
        </table>
      </td>
    </tr>
    """

    html = f"""
    <html>
    <body style="margin:0; padding:0; background:#f3f4f6;
                 font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">

      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 0;">
        <tr>
          <td align="center">

            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                   style="max-width:640px; background:#ffffff; border-radius:18px; overflow:hidden;
                          box-shadow:0 10px 28px rgba(0,0,0,0.10);">

              <!-- Top brand bars -->
              <tr>
                <td>
                  <div style="height:7px; background:{BRAND_BLUE};"></div>
                  <div style="height:7px; background:{BRAND_RED};"></div>
                </td>
              </tr>

              <tr>
                <td style="padding:30px;">

                  <!-- Header -->
                  <table role="presentation" width="100%">
                    <tr>
                      <td>
                        <div style="font-size:22px; font-weight:950; color:{BRAND_BLUE};">
                          Your Hero is Ready
                        </div>
                        <div style="margin-top:6px; font-size:13px; color:#6b7280;">
                          Download your personalized hero content below.
                        </div>
                      </td>
                      <td align="right" style="width:86px;">
                        {_brand_logo_tile(54)}
                      </td>
                    </tr>
                  </table>

                  <div style="height:18px;"></div>

                  <!-- Greeting -->
                  <div style="font-size:15px; color:#111827; line-height:1.6;">
                    Hi <strong>{safe_name}</strong>,<br/>
                    Thanks for visiting our hockey kiosk! Here’s your content:
                  </div>

                  <div style="height:18px;"></div>

                  {stacked_content_card}

                  <table role="presentation" width="100%">
                    {signature}
                  </table>

                </td>
              </tr>
            </table>

            <div style="height:14px;"></div>

            <div style="max-width:640px; font-size:11px; color:#9ca3af; text-align:center;">
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
    card_url: str,
    video_url: Optional[str] = None,
) -> None:
    if not (EMAIL_USERNAME and EMAIL_PASSWORD):
        raise RuntimeError("Email credentials not configured")

    subject = "Your Jersey Mike’s Hero is Ready!"

    safe_name = _format_name(first_name)
    plain_text = (
        f"Hi {safe_name},\n\n"
        f"Your hero content is ready.\n\n"
        f"Hero card: {card_url}\n"
    )
    if video_url:
        plain_text += f"Highlight video: {video_url}\n"
    plain_text += "\nIf you didn’t request this email, you can ignore it.\n"

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(plain_text)

    msg.add_alternative(
        _build_email_html(first_name, card_url, video_url),
        subtype="html",
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"[email_client] Sent result email to {to_email}")

