"""Rendering for the three fixed transactional email templates this service knows how to
send. Deliberately not a heavy templating engine (no Jinja2) - three fixed templates with a
handful of keys each is simple enough for plain f-strings, in the same "keep it simple" spirit
as agent-builder-service's app/services/prompt_template.py, though the shape here is
different: each template renders a (subject, text_body, html_body) triple rather than
substituting into a single caller-supplied string.

`template` must be one of TEMPLATE_NAMES - this is a fixed cross-service contract with
iam-service (the enqueuer). Unknown template names raise ValueError, which app.tasks treats
as a non-retryable programming error.
"""
from dataclasses import dataclass

TEMPLATE_NAMES = ("org_admin_invite", "user_invite", "password_reset")

_HTML_WRAPPER = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background-color:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:32px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;">
            <tr>
              <td style="background-color:#1f2937;padding:20px 32px;">
                <span style="color:#ffffff;font-size:18px;font-weight:bold;">TalentOS</span>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;color:#1f2937;font-size:15px;line-height:1.5;">
                {body}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px;color:#9ca3af;font-size:12px;border-top:1px solid #e5e7eb;">
                This is an automated message from TalentOS. If you weren't expecting it, you can safely ignore it.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

_BUTTON = (
    '<p style="margin:24px 0;">'
    '<a href="{url}" style="background-color:#2563eb;color:#ffffff;text-decoration:none;'
    'padding:12px 20px;border-radius:6px;display:inline-block;font-weight:bold;">{label}</a>'
    "</p>"
    '<p style="font-size:13px;color:#6b7280;word-break:break-all;">'
    "If the button doesn't work, copy and paste this link into your browser:<br>"
    '<a href="{url}" style="color:#2563eb;">{url}</a></p>'
)


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text_body: str
    html_body: str


def _wrap_html(inner_html: str) -> str:
    return _HTML_WRAPPER.format(body=inner_html)


def _render_org_admin_invite(context: dict) -> RenderedEmail:
    organization_name = context["organization_name"]
    display_name = context["display_name"]
    set_password_url = context["set_password_url"]

    subject = f"You've been made an admin of {organization_name} on TalentOS"

    text_body = (
        f"Hi {display_name},\n\n"
        f"You've been made an administrator of {organization_name} on TalentOS.\n\n"
        "As an admin, you'll be able to manage your organization's users, roles, and settings.\n\n"
        "Before you can log in, you need to set a password for your account. Use the link below:\n"
        f"{set_password_url}\n\n"
        "If you weren't expecting this invitation, you can safely ignore this email.\n"
    )

    html_body = _wrap_html(
        f'<p>Hi {display_name},</p>'
        f"<p>You've been made an <strong>administrator</strong> of "
        f"<strong>{organization_name}</strong> on TalentOS.</p>"
        "<p>As an admin, you'll be able to manage your organization's users, roles, and "
        "settings.</p>"
        "<p>Before you can log in, you need to set a password for your account.</p>"
        + _BUTTON.format(url=set_password_url, label="Set your password")
        + "<p>If you weren't expecting this invitation, you can safely ignore this email.</p>"
    )

    return RenderedEmail(subject=subject, text_body=text_body, html_body=html_body)


def _render_user_invite(context: dict) -> RenderedEmail:
    organization_name = context["organization_name"]
    display_name = context["display_name"]
    set_password_url = context["set_password_url"]

    subject = f"You've been invited to {organization_name} on TalentOS"

    text_body = (
        f"Hi {display_name},\n\n"
        f"You've been invited to join {organization_name} on TalentOS.\n\n"
        "Before you can log in, you need to set a password for your account. Use the link below:\n"
        f"{set_password_url}\n\n"
        "If you weren't expecting this invitation, you can safely ignore this email.\n"
    )

    html_body = _wrap_html(
        f'<p>Hi {display_name},</p>'
        f"<p>You've been invited to join <strong>{organization_name}</strong> on TalentOS.</p>"
        "<p>Before you can log in, you need to set a password for your account.</p>"
        + _BUTTON.format(url=set_password_url, label="Set your password")
        + "<p>If you weren't expecting this invitation, you can safely ignore this email.</p>"
    )

    return RenderedEmail(subject=subject, text_body=text_body, html_body=html_body)


def _render_password_reset(context: dict) -> RenderedEmail:
    display_name = context["display_name"]
    reset_url = context["reset_url"]

    subject = "Reset your TalentOS password"

    text_body = (
        f"Hi {display_name},\n\n"
        "We received a request to reset your TalentOS password. Use the link below to choose "
        "a new one:\n"
        f"{reset_url}\n\n"
        "This link expires soon. If you didn't request a password reset, you can safely "
        "ignore this email - your password will not be changed.\n"
    )

    html_body = _wrap_html(
        f'<p>Hi {display_name},</p>'
        "<p>We received a request to reset your TalentOS password.</p>"
        + _BUTTON.format(url=reset_url, label="Reset your password")
        + "<p>This link expires soon. If you didn't request a password reset, you can safely "
        "ignore this email - your password will not be changed.</p>"
    )

    return RenderedEmail(subject=subject, text_body=text_body, html_body=html_body)


_RENDERERS = {
    "org_admin_invite": _render_org_admin_invite,
    "user_invite": _render_user_invite,
    "password_reset": _render_password_reset,
}


def render_email(template: str, context: dict) -> RenderedEmail:
    """Raises ValueError for an unknown template, KeyError for a missing context key -
    both are treated as non-retryable programming errors by app.tasks."""
    if template not in _RENDERERS:
        raise ValueError(f"Unknown email template: {template!r} (expected one of {TEMPLATE_NAMES})")
    return _RENDERERS[template](context)
