from urllib.parse import quote

from app.providers.base import ProviderField
from app.providers.queue.base import QueueProvider


class PostgresQueueProvider(QueueProvider):
    """A PostgreSQL database used as the broker, via Kombu's SQLAlchemy transport. Same
    mechanism the platform itself uses for tier-1 ingest (see Settings.NOTIFICATIONS_BROKER_URL) -
    offered as a tenant provider too, for an organization that wants its notifications isolated
    in a database it controls without standing up Redis or RabbitMQ."""

    key = "postgres"
    label = "PostgreSQL"
    description = (
        "Use a PostgreSQL database as the message broker (Kombu SQLAlchemy transport). "
        "No extra infrastructure to run."
    )
    fields: tuple[ProviderField, ...] = (
        ProviderField(name="host", label="Host", placeholder="localhost"),
        ProviderField(name="port", label="Port", type="int", default=5432),
        ProviderField(name="database", label="Database", placeholder="talentos_notifications"),
        ProviderField(name="username", label="Username", required=False),
        ProviderField(name="password", label="Password", required=False, secret=True),
    )

    def broker_url(self) -> str:
        # "sqla+postgresql://" - Kombu's SQLAlchemy transport parses the scheme itself to pick
        # its dialect, so this is deliberately NOT the "postgresql+psycopg2://" form
        # SQLAlchemy's own create_engine() takes.
        username = self.config.get("username") or ""
        password = self.config.get("password") or ""
        credentials = ""
        if username:
            credentials = quote(username, safe="")
            if password:
                credentials = credentials + ":" + quote(password, safe="")
            credentials = credentials + "@"
        host = self.config["host"]
        port = self.config["port"]
        database = self.config["database"]
        return f"sqla+postgresql://{credentials}{host}:{port}/{database}"
