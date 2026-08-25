from urllib.parse import quote

from app.providers.base import ProviderField
from app.providers.queue.base import QueueProvider


class RabbitMqQueueProvider(QueueProvider):
    """RabbitMQ (AMQP 0-9-1) as the broker - the option for an organization that already runs
    AMQP infrastructure and wants its notifications to land in it."""

    key = "rabbitmq"
    label = "RabbitMQ (AMQP)"
    description = "Use a RabbitMQ / AMQP 0-9-1 broker."
    fields: tuple[ProviderField, ...] = (
        ProviderField(name="host", label="Host", placeholder="localhost"),
        ProviderField(name="port", label="Port", type="int", default=5672),
        ProviderField(name="username", label="Username", default="guest"),
        ProviderField(name="password", label="Password", secret=True),
        ProviderField(name="vhost", label="Virtual host", required=False, default="/"),
        ProviderField(name="use_tls", label="Use TLS (amqps)", type="bool", required=False),
    )

    def broker_url(self) -> str:
        scheme = "amqps" if self.config.get("use_tls") else "amqp"
        vhost = self.config.get("vhost") or "/"
        # A vhost is a path segment, so the default vhost is an EMPTY path, and any other name
        # has to be percent-encoded whole: a vhost literally named "/prod" is a different vhost
        # from one named "prod", and only encoding tells them apart on the wire.
        vhost_path = "" if vhost == "/" else quote(vhost, safe="")
        username = quote(self.config["username"], safe="")
        password = quote(self.config["password"], safe="")
        host = self.config["host"]
        port = self.config["port"]
        return f"{scheme}://{username}:{password}@{host}:{port}/{vhost_path}"
