import httpx

from app.providers.base import ProviderField, ProviderSendError
from app.providers.email.base import EmailProvider
from app.templates import RenderedEmail

_SEND_ENDPOINT = "https://api.sendgrid.com/v3/mail/send"
_SCOPES_ENDPOINT = "https://api.sendgrid.com/v3/scopes"


class SendGridEmailProvider(EmailProvider):
    """SendGrid's v3 HTTP API - the provider an organization picks when they would rather not
    expose an SMTP relay. Included as the second email provider mainly to prove the abstraction
    holds for something that is not SMTP-shaped at all: a different transport, a different auth
    model, a different failure vocabulary, and none of that leaks past EmailProvider.send."""

    key = "sendgrid"
    label = "SendGrid"
    description = "Send through SendGrid's v3 HTTP API using an API key."
    fields: tuple[ProviderField, ...] = (
        ProviderField(name="api_key", label="API key", secret=True, placeholder="SG.xxxxxxxx"),
        ProviderField(name="from_address", label="From address", type="email", placeholder="no-reply@yourcompany.com"),
        ProviderField(name="from_name", label="From name", required=False),
        ProviderField(name="timeout_seconds", label="Timeout (seconds)", type="int", required=False, default=20),
    )

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.config['api_key']}", "Content-Type": "application/json"}

    def send(self, *, to_email: str, rendered: RenderedEmail) -> str:
        sender: dict = {"email": self.config["from_address"]}
        if self.config.get("from_name"):
            sender["name"] = self.config["from_name"]
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": sender,
            "subject": rendered.subject,
            "content": [
                {"type": "text/plain", "value": rendered.text_body},
                {"type": "text/html", "value": rendered.html_body},
            ],
        }
        try:
            response = httpx.post(
                _SEND_ENDPOINT,
                json=payload,
                headers=self._headers(),
                timeout=float(self.config.get("timeout_seconds", 20)),
            )
        except httpx.HTTPError as exc:
            raise ProviderSendError(f"SendGrid request failed: {exc}") from exc
        if response.status_code >= 300:
            raise ProviderSendError(f"SendGrid rejected the message ({response.status_code}): {response.text[:300]}")
        return "sent"

    def verify(self) -> str:
        """Hits /v3/scopes rather than sending a message: it proves the API key is valid and
        authorised without putting a real email on someone's doorstep."""
        try:
            response = httpx.get(
                _SCOPES_ENDPOINT, headers=self._headers(), timeout=float(self.config.get("timeout_seconds", 20))
            )
        except httpx.HTTPError as exc:
            raise ProviderSendError(f"SendGrid request failed: {exc}") from exc
        if response.status_code >= 300:
            raise ProviderSendError(f"SendGrid rejected the API key ({response.status_code}): {response.text[:300]}")
        return "API key accepted by SendGrid."
