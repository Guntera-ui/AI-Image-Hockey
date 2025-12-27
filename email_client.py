from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.mime.image import MIMEImage
from pathlib import Path
from typing import Optional

from config import (
    EMAIL_FROM,
    EMAIL_PASSWORD,
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_USERNAME,
)

# -------------------------------------------------------------------
# Embedded image CIDs
# -------------------------------------------------------------------

CID_TOP = "email_top"
CID_BOTTOM = "email_bottom"

DOWNLOAD_BASE = "https://jerseymikespowerplay.com/download"
ORDER_NOW_URL = (
    "https://www.jerseymikes.com/menu?"
    "msclkid=7b30a333110c196efe95ca7f397ae0f5"
    "&utm_source=bing&utm_medium=cpc"
    "&utm_campaign=Search+-+Brand"
    "&utm_term=jersey+mike%27s+menu"
    "&utm_content=Menu"
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _format_name(first_name: Optional[str]) -> str:
    return first_name.strip() if first_name else "there"


def _download_link_for_run(unique_id: str) -> str:
    return f"{DOWNLOAD_BASE}/{unique_id}"


# -------------------------------------------------------------------
# HTML builder
# -------------------------------------------------------------------

def _build_email_html(first_name: str, unique_id: str) -> str:
    name = _format_name(first_name)
    download_url = _download_link_for_run(unique_id)

    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background:#ffffff;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;">
<tr>
<td align="center">

<table width="600" cellpadding="0" cellspacing="0"
       style="background:#ffffff; margin:0; padding:0;">

<!-- TOP IMAGE -->
<tr>
<td style="padding:0; line-height:0; font-size:0;">
<img src="cid:{CID_TOP}" width="600"
     style="display:block; border:0; outline:none;" />
</td>
</tr>

<!-- HEADLINE (RESTORED) -->
<tr>
<td align="center" style="
  padding:18px 28px 6px 28px;
  font-family:Arial, Helvetica, sans-serif;
  font-size:26px;
  line-height:32px;
  font-weight:900;
  color:#134A7C;">
Your Jersey Mike’s Power Play Video Is Ready!
</td>
</tr>

<!-- BODY TEXT -->
<tr>
<td style="
  padding:16px 28px 16px 28px;
  font-family:Arial, Helvetica, sans-serif;
  color:#134A7C;
  font-size:18px;
  line-height:26px;
  font-weight:600;">
<strong>Hi {name},</strong><br><br>
Thanks for joining the Jersey Mike’s Power Play hockey experience!
Your custom photo and AI video are ready — watch yourself in full ice hockey
gear taking the perfect shot on goal.
</td>
</tr>

<!-- DOWNLOAD LINK -->
<tr>
<td style="
  padding:0 28px 18px 28px;
  font-family:Arial, Helvetica, sans-serif;
  font-size:18px;
  font-weight:700;">
<a href="{download_url}"
   style="color:#134A7C; text-decoration:underline;">
Download Your Video
</a>
</td>
</tr>

<!-- SHARE TEXT -->
<tr>
<td style="
  padding:0 28px 24px 28px;
  font-family:Arial, Helvetica, sans-serif;
  font-size:18px;
  line-height:26px;
  color:#134A7C;
  font-weight:600;">
Think you nailed it? Share your epic shot with friends and show off your
inner hockey star!
</td>
</tr>

<!-- SIGNATURE -->
<tr>
<td style="
  padding:0 28px 14px 28px;
  font-family:Arial, Helvetica, sans-serif;
  font-size:18px;
  font-weight:600;
  color:#134A7C;">
Cheers,<br>
Jersey Mike’s
</td>
</tr>

<!-- ORDER NOW BUTTON -->
<tr>
<td align="center" style="padding:10px 0 30px 0;">
  <table cellpadding="0" cellspacing="0" role="presentation">
    <tr>
      <td style="
        background:#134A7C;
        border-radius:18px;
        padding:4px;">
        <a href="{ORDER_NOW_URL}"
           style="
             display:block;
             background:#134A7C;
             border:2px solid #ffffff;
             border-radius:14px;
             padding:12px 34px;
             font-family:Arial, Helvetica, sans-serif;
             font-size:16px;
             font-weight:900;
             letter-spacing:2px;
             color:#ffffff;
             text-decoration:none;
             text-align:center;">
          ORDER&nbsp;NOW
        </a>
      </td>
    </tr>
  </table>
</td>
</tr>

<!-- BOTTOM IMAGE -->
<tr>
<td style="padding:0; line-height:0; font-size:0;">
<img src="cid:{CID_BOTTOM}" width="600"
     style="display:block; border:0; outline:none;" />
</td>
</tr>

</table>

</td>
</tr>
</table>
</body>
</html>
"""


# -------------------------------------------------------------------
# Send function
# -------------------------------------------------------------------

def send_player_result_email(
    *,
    to_email: str,
    run_id: str,
    first_name: Optional[str] = "",
    total_score: Optional[int] = None,  # intentionally ignored
) -> None:

    if not (EMAIL_USERNAME and EMAIL_PASSWORD):
        raise RuntimeError("Email credentials not configured")

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = "Your Jersey Mike’s Power Play Video Is Ready!"

    text_fallback = f"""Hi {first_name or "there"},

Your Jersey Mike’s Power Play video is ready!

Download your video:
{_download_link_for_run(run_id)}

Order now:
{ORDER_NOW_URL}

Cheers,
Jersey Mike’s
"""

    msg.set_content(text_fallback)
    msg.add_alternative(
        _build_email_html(first_name or "", run_id),
        subtype="html",
    )

    html_part = msg.get_payload()[1]

    for cid, path in (
        (CID_TOP, "assets/overlays/email_top.png"),
        (CID_BOTTOM, "assets/overlays/email_bottom.png"),
    ):
        with open(path, "rb") as f:
            img = MIMEImage(f.read())
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header(
                "Content-Disposition",
                "inline",
                filename=Path(path).name,
            )
            html_part.add_related(img)

    context = ssl.create_default_context()
    with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"[email_client] Sent result email to {to_email} (uniqueId={run_id})")

