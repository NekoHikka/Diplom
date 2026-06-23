import smtplib
from email.message import EmailMessage
from html import escape

from flask import current_app

from app.utils.strings import get_string


class EmailService:
    @staticmethod
    def _smtp_configured():
        return bool(
            current_app.config.get('MAIL_SERVER')
            and current_app.config.get('MAIL_USERNAME')
            and current_app.config.get('MAIL_PASSWORD')
            and current_app.config.get('MAIL_DEFAULT_SENDER')
        )

    @staticmethod
    def send_code(to_email, code, purpose, lang='uk'):
        subject_key = (
            'email_subject_verify'
            if purpose == 'verify_email'
            else 'email_subject_reset'
        )
        body_key = (
            'email_body_verify'
            if purpose == 'verify_email'
            else 'email_body_reset'
        )

        subject = get_string(subject_key, lang=lang)
        body = get_string(body_key, lang=lang, code=code)
        preview = get_string('email_preview', lang=lang)
        html_body = EmailService._build_html_message(subject, preview, body, code)

        if not EmailService._smtp_configured():
            if current_app.config.get('MAIL_DEBUG_PRINT_CODES'):
                current_app.logger.warning("Email code for %s: %s", to_email, code)
                return True
            current_app.logger.error("SMTP is not configured; email was not sent.")
            return False

        message = EmailMessage()
        message['Subject'] = subject
        message['From'] = f"Smart Finance <{current_app.config['MAIL_DEFAULT_SENDER']}>"
        message['To'] = to_email
        message['Reply-To'] = current_app.config['MAIL_DEFAULT_SENDER']
        message['Auto-Submitted'] = 'auto-generated'
        message['X-Auto-Response-Suppress'] = 'All'
        message.set_content(body)
        message.add_alternative(html_body, subtype='html')

        server = current_app.config['MAIL_SERVER']
        port = current_app.config['MAIL_PORT']
        username = current_app.config['MAIL_USERNAME']
        password = current_app.config['MAIL_PASSWORD']

        try:
            if current_app.config.get('MAIL_USE_SSL'):
                with smtplib.SMTP_SSL(server, port, timeout=15) as smtp:
                    smtp.login(username, password)
                    smtp.send_message(message)
            else:
                with smtplib.SMTP(server, port, timeout=15) as smtp:
                    if current_app.config.get('MAIL_USE_TLS'):
                        smtp.starttls()
                    smtp.login(username, password)
                    smtp.send_message(message)
            return True
        except Exception as exc:
            current_app.logger.exception("Failed to send email code: %s", exc)
            return False

    @staticmethod
    def _build_html_message(title, preview, body, code):
        safe_title = escape(title)
        safe_preview = escape(preview)
        safe_body = '<br>'.join(escape(body).splitlines())
        safe_code = escape(code)

        return f"""<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;color:#1f2937;">
    <span style="display:none;visibility:hidden;opacity:0;height:0;width:0;overflow:hidden;">{safe_preview}</span>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f7fb;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:480px;background:#ffffff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden;">
            <tr>
              <td style="padding:22px 24px;background:#111827;color:#ffffff;font-size:20px;font-weight:bold;">
                Smart Finance
              </td>
            </tr>
            <tr>
              <td style="padding:24px;">
                <h1 style="margin:0 0 16px;font-size:22px;line-height:1.3;color:#111827;">{safe_title}</h1>
                <div style="font-size:34px;letter-spacing:8px;font-weight:bold;color:#2196f3;background:#eef6ff;border-radius:10px;padding:16px;text-align:center;margin:18px 0;">{safe_code}</div>
                <p style="font-size:15px;line-height:1.6;margin:0;color:#374151;">{safe_body}</p>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 24px;background:#f9fafb;color:#6b7280;font-size:12px;line-height:1.5;">
                This is an automatic security message from Smart Finance. Please do not reply to this email.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
