from abc import abstractmethod

import kombu

from app.providers.base import Provider, ProviderSendError


class QueueProvider(Provider):
    """Which broker an organization's notifications are dispatched onto.

    Every implementation reduces to one thing - a Kombu broker URL plus optional transport
    options - because Celery/Kombu already abstracts the wire protocol. That is the whole reason
    a tenant can bring "their own queue service" without this service growing a driver per
    vendor: Postgres, Redis, RabbitMQ and SQS are four URL shapes over one client.

    verify() opens a real connection, so the "Test connection" button fails fast on a typo
    rather than at 3am when an invite silently never arrives."""

    kind = "queue"

    @abstractmethod
    def broker_url(self) -> str:
        """The Kombu/Celery broker URL this config resolves to. May embed credentials - which is
        exactly why the fields that make it up are declared secret and encrypted at rest."""

    def transport_options(self) -> dict:
        return {}

    def verify(self) -> str:
        url = self.broker_url()
        try:
            with kombu.Connection(url, transport_options=self.transport_options(), connect_timeout=10) as connection:
                connection.ensure_connection(max_retries=0, timeout=10)
        except Exception as exc:  # kombu raises a wide, transport-specific set here
            raise ProviderSendError(f"Could not connect to the broker: {exc}") from exc
        return "Broker connection established."
