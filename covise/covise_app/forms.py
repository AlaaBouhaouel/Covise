import logging

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template import loader

try:
    import resend
except ImportError:
    resend = None


logger = logging.getLogger(__name__)
RESEND_API_KEY = getattr(settings, "RESEND_API_KEY", getattr(settings, "RESEND_API", ""))
PASSWORD_RESET_FROM_EMAIL = getattr(settings, "PASSWORD_RESET_FROM_EMAIL", "CoVise <founders@covise.net>")


class CoVisePasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines()).strip()
        body = loader.render_to_string(email_template_name, context)
        html_body = (
            loader.render_to_string(html_email_template_name, context)
            if html_email_template_name
            else None
        )
        sender = from_email or PASSWORD_RESET_FROM_EMAIL

        if resend is not None and RESEND_API_KEY:
            try:
                resend.api_key = RESEND_API_KEY
                payload = {
                    "from": sender,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                }
                if html_body:
                    payload["html"] = html_body
                resend.Emails.send(payload)
                return
            except Exception:
                logger.exception("Failed to send password reset email via Resend to %s", to_email)

        email_message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=sender,
            to=[to_email],
        )
        if html_body:
            email_message.attach_alternative(html_body, "text/html")
        email_message.send(fail_silently=False)
