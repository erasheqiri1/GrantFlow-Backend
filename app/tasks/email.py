import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.celery_app import celery_app
from app.core.config import settings


<<<<<<< Updated upstream
def _send_smtp(to: str, subject: str, html: str) -> None:
    """Dërgon email direkt nëpërmjet Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.MAIL_FROM or settings.MAIL_USERNAME
    msg["To"]      = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
        server.sendmail(msg["From"], to, msg.as_string())


@celery_app.task(name="send_invitation_email", bind=True, max_retries=3)
def send_invitation_email(self, to: str, invite_link: str, role: str, org_name: str = "") -> dict:
    """
    Task Celery — dërgon email ftese në background.
    Provohet deri në 3 herë nëse dështon.
    """
    try:
        role_label = {
            "SUPER_ADMIN":  "Super Admin",
            "ORG_ADMIN":    "Admin Organizate",
            "COMMISSIONER": "Komisioner",
        }.get(role, role)

        org_line = f"<p>Organizata: <strong>{org_name}</strong></p>" if org_name else ""

        html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:auto;padding:32px;
                    background:#0f1117;border-radius:12px;color:#e2e8f0;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:24px;font-weight:900;letter-spacing:1px;">
              <span style="color:#fff;">GRANT</span><span style="color:#6366f1;">FLOW</span>
            </span>
          </div>
          <h2 style="color:#fff;margin-bottom:8px;">Ju jeni ftuar në GrantFlow</h2>
          <p>Ju është dërguar një ftesë si <strong style="color:#6366f1;">{role_label}</strong>.</p>
          {org_line}
          <p>Klikoni butonin më poshtë për të aktivizuar llogarinë tuaj:</p>
          <div style="text-align:center;margin:28px 0;">
            <a href="{invite_link}"
               style="background:#6366f1;color:#fff;padding:12px 28px;border-radius:8px;
                      text-decoration:none;font-weight:600;font-size:15px;">
              Aktivizo llogarinë →
            </a>
          </div>
          <p style="color:#64748b;font-size:12px;">
            Ky link skadon pas 48 orësh. Nëse nuk e pritët këtë email, injoroni.
          </p>
        </div>
        """

        _send_smtp(to, f"Ftesë për GrantFlow — {role_label}", html)
        return {"status": "sent", "to": to}

    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)  # riprovon pas 60 sekondave
=======
@celery_app.task(bind=True, max_retries=3)
def send_invitation_email(self, to: str, invite_link: str, role: str, org_name: str):
    role_labels = {
        "SUPER_ADMIN": "Super Administrator",
        "ORG_ADMIN": "Administrator Organizate",
        "COMMISSIONER": "Komisioner",
        "REVIEWER": "Recensues",
    }
    role_label = role_labels.get(role, role)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 8px;
                      box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow: hidden; }}
        .header {{ background: #2563eb; color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .body {{ padding: 30px; color: #333; }}
        .body p {{ line-height: 1.6; }}
        .btn {{ display: inline-block; background: #2563eb; color: white; padding: 14px 28px;
                border-radius: 6px; text-decoration: none; font-weight: bold; margin: 20px 0; }}
        .footer {{ padding: 20px 30px; background: #f9f9f9; font-size: 12px; color: #888;
                   text-align: center; border-top: 1px solid #eee; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>GrantFlow</h1>
          <p style="margin:8px 0 0; opacity:0.9;">Ftesë për t'u bashkuar</p>
        </div>
        <div class="body">
          <p>Përshëndetje,</p>
          <p>Jeni ftuar të bashkoheni me <strong>{org_name}</strong> si <strong>{role_label}</strong> në platformën GrantFlow.</p>
          <p>Klikoni butonin më poshtë për të aktivizuar llogarinë tuaj. Ftesa është e vlefshme për <strong>7 ditë</strong>.</p>
          <p style="text-align: center;">
            <a href="{invite_link}" class="btn">Aktivizo Llogarinë</a>
          </p>
          <p>Nëse nuk mund të klikoni butonin, kopjojeni këtë link në shfletues:</p>
          <p style="word-break: break-all; font-size: 13px; color: #555;">{invite_link}</p>
          <p>Nëse nuk e keni kërkuar këtë ftesë, mund ta injoroni këtë email.</p>
        </div>
        <div class="footer">
          &copy; 2025 GrantFlow &mdash; Platforma e Menaxhimit të Granteve
        </div>
      </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Ftesë për GrantFlow — {org_name}"
    msg["From"] = settings.MAIL_FROM
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.sendmail(settings.MAIL_FROM, to, msg.as_string())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
>>>>>>> Stashed changes
