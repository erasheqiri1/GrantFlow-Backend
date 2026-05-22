import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.celery_app import celery_app
from app.core.config import settings


def _send_smtp(to: str, subject: str, html: str) -> None:
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


@celery_app.task(name="send_reset_password_email", bind=True, max_retries=3)
def send_reset_password_email(self, to: str, reset_link: str) -> dict:
    try:
        html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:auto;padding:32px;
                    background:#0f1117;border-radius:12px;color:#e2e8f0;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:24px;font-weight:900;">
              <span style="color:#fff;">GRANT</span><span style="color:#6366f1;">FLOW</span>
            </span>
          </div>
          <h2 style="color:#fff;">Rivendosja e fjalëkalimit</h2>
          <p>Kemi marrë kërkesën për rivendosjen e fjalëkalimit tuaj.</p>
          <div style="text-align:center;margin:28px 0;">
            <a href="{reset_link}"
               style="background:#6366f1;color:#fff;padding:12px 28px;border-radius:8px;
                      text-decoration:none;font-weight:600;">
              Rivendos fjalëkalimin →
            </a>
          </div>
          <p style="color:#64748b;font-size:12px;">Ky link skadon pas 1 ore. Nëse nuk e kërkuat ju, injoroni këtë email.</p>
        </div>
        """
        _send_smtp(to, "Rivendosja e fjalëkalimit — GrantFlow", html)
        return {"status": "sent", "to": to}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="send_invitation_email", bind=True, max_retries=3)
def send_invitation_email(self, to: str, invite_link: str, role: str, org_name: str = "") -> dict:
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
            <span style="font-size:24px;font-weight:900;">
              <span style="color:#fff;">GRANT</span><span style="color:#6366f1;">FLOW</span>
            </span>
          </div>
          <h2 style="color:#fff;">Ju jeni ftuar në GrantFlow</h2>
          <p>Ftesë si <strong style="color:#6366f1;">{role_label}</strong>.</p>
          {org_line}
          <div style="text-align:center;margin:28px 0;">
            <a href="{invite_link}"
               style="background:#6366f1;color:#fff;padding:12px 28px;border-radius:8px;
                      text-decoration:none;font-weight:600;">
              Aktivizo llogarinë →
            </a>
          </div>
          <p style="color:#64748b;font-size:12px;">Ky link skadon pas 48 orësh.</p>
        </div>
        """

        _send_smtp(to, f"Ftesë për GrantFlow — {role_label}", html)
        return {"status": "sent", "to": to}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
