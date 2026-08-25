import smtplib
import ssl
from email.message import EmailMessage

from app.providers.base import ProviderField, ProviderSendError
from app.providers.email.base import EmailProvider
from app.templates import RenderedEmail


class SmtpEmailProvider(EmailProvider):
    """Plain SMTP via the standard library - the provider an organization picks to point
    TalentOS at their own mail relay (Google Workspace, Microsoft 365, Amazon SES's SMTP
    interface, an internal Postfix, ...).

    Both a multipart text and HTML body are attached, in that order, so a client that cannot
    render HTML still gets a usable message containing the link."""

    key = "smtp"
    label = "SMTP"
    description = "Send through any SMTP relay - your own mail server, Google Workspace, Microsoft 365, SES SMTP."
    fields: tuple[ProviderField, ...] = (
        ProviderField(name="host", label="SMTP host", placeholder="smtp.example.com"),
        ProviderField(name="port", label="Port", type="int", default=587),
        ProviderField(name="username", label="Username", required=False),
        ProviderField(name="password", label="Password", required=False, secret=True),
        ProviderField(name="from_address", label="From address", type="email", placeholder="no-reply@yourcompany.com"),
        ProviderField(name="from_name", label="From name", required=False, placeholder="YourCompany"),
        ProviderField(
            name="use_tls",
            label="Use STARTTLS",
            type="bool",
            required=False,
            default=True,
            help="STARTTLS on a plain connection (port 587). Turn off only for an internal relay on a trusted network.",
        ),
        ProviderField(
            name="use_ssl",
            label="Use implicit SSL",
            type="bool",
            required=False,
            help="Connect over TLS from the first byte (port 465). Mutually exclusive with STARTTLS.",
        ),
        ProviderField(
            name="verify_cert",
            label="Verify the server's TLS certificate",
            type="bool",
            required=False,
            default=True,
            help=(
                "Leave on unless your relay presents a self-signed or internal-CA certificate. "
                "Turning it off keeps the connection encrypted but stops proving the server is "
                "who it claims to be, so only do it on a network you trust."
            ),
        ),
        ProviderField(name="timeout_seconds", label="Timeout (seconds)", type="int", required=False, default=20),
    )

    def _ssl_context(self) -> ssl.SSLContext:
        """Certificate verification is on by default and has to be switched off deliberately.

        An internal relay with a self-signed certificate is a real and common case - but the
        failure it produces (CERTIFICATE_VERIFY_FAILED) is easy to "fix" by disabling TLS
        altogether, which would put the SMTP password on the wire in clear. This keeps the
        connection encrypted and drops only the identity check, which is the much smaller
        concession of the two."""
        context = ssl.create_default_context()
        if not self.config.get("verify_cert", True):
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    def _connect(self) -> smtplib.SMTP:
        host = self.config["host"]
        port = int(self.config.get("port", 587))
        timeout = int(self.config.get("timeout_seconds", 20))
        try:
            if self.config.get("use_ssl"):
                client: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=self._ssl_context())
            else:
                client = smtplib.SMTP(host, port, timeout=timeout)
                if self.config.get("use_tls", True):
                    client.starttls(context=self._ssl_context())
            username = self.config.get("username")
            if username:
                client.login(username, self.config.get("password") or "")
            return client
        except (OSError, smtplib.SMTPException) as exc:
            raise ProviderSendError(f"SMTP connection to {host}:{port} failed: {exc}") from exc

    def _from_header(self) -> str:
        address = self.config["from_address"]
        name = self.config.get("from_name")
        return f"{name} <{address}>" if name else address

    def send(self, *, to_email: str, rendered: RenderedEmail) -> str:
        message = EmailMessage()
        message["Subject"] = rendered.subject
        message["From"] = self._from_header()
        message["To"] = to_email
        message.set_content(rendered.text_body)
        message.add_alternative(rendered.html_body, subtype="html")

        client = self._connect()
        try:
            client.send_message(message)
        except smtplib.SMTPException as exc:
            raise ProviderSendError(f"SMTP send to {to_email} failed: {exc}") from exc
        finally:
            try:
                client.quit()
            except smtplib.SMTPException:
                pass
        return "sent"

    def verify(self) -> str:
        client = self._connect()
        try:
            client.noop()
        finally:
            try:
                client.quit()
            except smtplib.SMTPException:
                pass
        return f"Connected and authenticated to {self.config['host']}:{self.config.get('port', 587)}."
