from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from messaging.services.brevo import BrevoError, post_plain_email


def password_set_url(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
    return request.build_absolute_uri(path)


def send_password_mail(request, user):
    url = password_set_url(request, user)
    context = {"user": user, "protocol": "https" if request.is_secure() else "http", "url": url}
    subject = "Set your service scheduler password"
    body = render_to_string("registration/password_reset_email.txt", context)
    try:
        post_plain_email(to=[user.email], subject=subject, body=body)
    except BrevoError:
        if settings.DEBUG:
            print(body)
            return
        raise


class BrevoPasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        # PasswordResetForm.save does not put the request in this context.
        # The token it already minted is the one the link must use.
        path = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": context["uid"], "token": context["token"]},
        )
        body_context = {
            **context,
            "url": f"{context['protocol']}://{context['domain']}{path}",
        }
        subject = render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines()).strip()
        body = render_to_string(email_template_name, body_context)
        try:
            post_plain_email(to=[to_email], subject=subject, body=body)
        except BrevoError:
            if settings.DEBUG:
                print(body)
                return
            raise
