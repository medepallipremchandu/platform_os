from abc import abstractmethod

from app.providers.base import Provider
from app.templates import RenderedEmail


class EmailProvider(Provider):
    """How an organization's transactional mail physically leaves the platform.

    `send` is called once per email by app.tasks.deliver_email. It must raise
    ProviderSendError for anything transient (connection refused, 4xx/5xx from an API, auth
    rejected) so Celery's retry/backoff applies, and it must NOT swallow failures - a silently
    dropped invite is worse than a retried one."""

    kind = "email"

    @abstractmethod
    def send(self, *, to_email: str, rendered: RenderedEmail) -> str:
        """Deliver one email. Returns the EmailLog status to record - normally "sent", but a
        provider that only logs (see ConsoleEmailProvider) reports that honestly instead."""
