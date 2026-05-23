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


@celery_app.task(name="send_verification_email", bind=True, max_retries=3)
def send_verification_email(self, to: str, verify_link: str, full_name: str) -> dict:
    try:
        html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:auto;padding:32px;
                    background:#0f1117;border-radius:12px;color:#e2e8f0;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:24px;font-weight:900;">
              <span style="color:#fff;">GRANT</span><span style="color:#6366f1;">FLOW</span>
            </span>
          </div>
          <h2 style="color:#fff;">Konfirmo adresën tënde të emailit</h2>
          <p>Përshëndetje <strong>{full_name}</strong>,</p>
          <p>Faleminderit që u regjistruat në GrantFlow. Për të vazhduar,
             ju lutemi konfirmoni adresën tuaj të emailit duke klikuar butonin më poshtë.</p>
          <div style="text-align:center;margin:28px 0;">
            <a href="{verify_link}"
               style="background:#6366f1;color:#fff;padding:12px 28px;border-radius:8px;
                      text-decoration:none;font-weight:600;">
              Konfirmo Emailin &#8594;
            </a>
          </div>
          <p style="color:#64748b;font-size:12px;">
            Ky link është i vlefshëm për <strong>24 orë</strong>.<br>
            Nëse nuk e keni kërkuar këtë, mund ta injoroni këtë email.
          </p>
        </div>
        """
        _send_smtp(to, "GrantFlow — Konfirmo Emailin Tend", html)
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


@celery_app.task(name="send_application_result_email", bind=True, max_retries=3)
def send_application_result_email(self, to: str, full_name: str, grant_title: str, approved: bool, reason: str = "") -> dict:
    try:
        if approved:
            color   = "#22c55e"
            heading = "Urime! Aplikimi juaj u aprovua 🎉"
            body    = f"Jemi të lumtur t'ju njoftojmë se aplikimi juaj për grantin <strong style=\"color:#6366f1;\">{grant_title}</strong> u aprovua nga organizata."
            extra   = ""
        else:
            color   = "#ef4444"
            heading = "Aplikimi juaj nuk u aprovua"
            body    = f"Pas shqyrtimit, aplikimi juaj për grantin <strong style=\"color:#6366f1;\">{grant_title}</strong> nuk u aprovua."
            extra   = f"<p style=\"color:#94a3b8;\"><strong>Arsyeja:</strong> {reason}</p>" if reason else ""

        html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:auto;padding:32px;
                    background:#0f1117;border-radius:12px;color:#e2e8f0;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:24px;font-weight:900;">
              <span style="color:#fff;">GRANT</span><span style="color:#6366f1;">FLOW</span>
            </span>
          </div>
          <h2 style="color:{color};">{heading}</h2>
          <p>Përshëndetje <strong>{full_name}</strong>,</p>
          <p>{body}</p>
          {extra}
          <p style="color:#64748b;font-size:12px;margin-top:24px;">
            Mund të identifikoheni në platformë për të parë detajet e plotë.
          </p>
        </div>
        """

        subject = f"GrantFlow — {'Aplikimi u aprovua' if approved else 'Aplikimi nuk u aprovua'}: {grant_title}"
        _send_smtp(to, subject, html)
        return {"status": "sent", "to": to}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="send_org_approval_email", bind=True, max_retries=3)
def send_org_approval_email(self, to: str, org_name: str, full_name: str, login_url: str) -> dict:
    try:
        html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:auto;padding:32px;
                    background:#0f1117;border-radius:12px;color:#e2e8f0;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:24px;font-weight:900;">
              <span style="color:#fff;">GRANT</span><span style="color:#6366f1;">FLOW</span>
            </span>
          </div>
          <h2 style="color:#22c55e;">Organizata juaj u aprovua!</h2>
          <p>Përshëndetje <strong>{full_name}</strong>,</p>
          <p>Jemi të lumtur t'ju njoftojmë se organizata
             <strong style="color:#6366f1;">{org_name}</strong>
             u aprovua nga administratori i platformës GrantFlow.</p>
          <p>Tani mund të kyçeni dhe të filloni të menaxhoni grantet tuaja.</p>
          <div style="text-align:center;margin:28px 0;">
            <a href="{login_url}"
               style="background:#22c55e;color:#fff;padding:12px 28px;border-radius:8px;
                      text-decoration:none;font-weight:600;">
              Kyçu në GrantFlow →
            </a>
          </div>
        </div>
        """
        _send_smtp(to, f"GrantFlow — Organizata '{org_name}' u Aprovua", html)
        return {"status": "sent", "to": to}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="send_org_rejection_email", bind=True, max_retries=3)
def send_org_rejection_email(self, to: str, org_name: str, full_name: str) -> dict:
    try:
        html = f"""
        <div style="font-family:sans-serif;max-width:520px;margin:auto;padding:32px;
                    background:#0f1117;border-radius:12px;color:#e2e8f0;">
          <div style="text-align:center;margin-bottom:24px;">
            <span style="font-size:24px;font-weight:900;">
              <span style="color:#fff;">GRANT</span><span style="color:#6366f1;">FLOW</span>
            </span>
          </div>
          <h2 style="color:#ef4444;">Organizata juaj nuk u aprovua</h2>
          <p>Përshëndetje <strong>{full_name}</strong>,</p>
          <p>Pas shqyrtimit, aplikimi i organizatës
             <strong style="color:#6366f1;">{org_name}</strong>
             nuk u aprovua nga administratori i platformës GrantFlow.</p>
          <p style="color:#94a3b8;">Nëse besoni se kjo është një gabim ose dëshironi
             më shumë informacion, ju lutemi na kontaktoni.</p>
        </div>
        """
        _send_smtp(to, f"GrantFlow — Aplikimi i '{org_name}' Nuk u Aprovua", html)
        return {"status": "sent", "to": to}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)