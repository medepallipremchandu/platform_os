import logging

from app.providers.base import ProviderField
from app.providers.email.base import EmailProvider
from app.templates import RenderedEmail

logger = logging.getLogger("app.providers.email.console")


class ConsoleEmailProvider(EmailProvider):
    """The sink used when no email provider is configured anywhere - not a tenant-selectable
    provider so much as the platform's honest fallback. The fully-rendered email is written to
    the log at INFO, INCLUDING the set-password / reset link, which is what makes the whole
    invite and forgot-password flow exercisable end-to-end in a sandbox with no SMTP
    credentials. It reports its EmailLog status as "logged_no_smtp_configured" rather than
    "sent" so an operator is never misled into thinking mail actually went out.

    This mirrors the convention iam-service's password_reset_service already used before this
    service existed."""

    key = "console"
    label = "Console (log only)"
    description = (
        "Writes the fully rendered email - including any set-password or reset link - to the "
        "service log instead of sending it. The platform fallback when no email provider is "
        "configured; never use it where real mail is expected to arrive."
    )
    fields: tuple[ProviderField, ...] = (
        ProviderField(
            name="from_address",
            label="From address",
            type="email",
            required=False,
            default="no-reply@talentos-platform.com",
        ),
    )

    def send(self, *, to_email: str, rendered: RenderedEmail) -> str:
        logger.info(
            "NO EMAIL PROVIDER CONFIGURED - email not sent, logged instead.\n"
            "  From:    %s\n  To:      %s\n  Subject: %s\n--- body ---\n%s\n--- end body ---",
            self.config.get("from_address"),
            to_email,
            rendered.subject,
            rendered.text_body,
        )
        return "logged_no_smtp_configured"

    def verify(self) -> str:
        return "Console provider is always available (emails are logged, not sent)."
