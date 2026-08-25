from urllib.parse import quote

from app.providers.base import ProviderField
from app.providers.queue.base import QueueProvider


class RedisQueueProvider(QueueProvider):
    """Redis - or anything speaking its protocol (ElastiCache, Upstash, Azure Cache) - as the
    broker. The most common Celery deployment, and the first thing most organizations bringing
    their own queue will reach for."""

    key = "redis"
    label = "Redis"
    description = "Use a Redis instance as the message broker."
    fields: tuple[ProviderField, ...] = (
        ProviderField(name="host", label="Host", placeholder="localhost"),
        ProviderField(name="port", label="Port", type="int", default=6379),
        ProviderField(name="db", label="Database number", type="int", required=False, default=0),
        ProviderField(
            name="username",
            label="Username",
            required=False,
            help="Redis 6+ ACL user. Leave blank to use the default user.",
        ),
        ProviderField(name="password", label="Password", required=False, secret=True),
        ProviderField(name="use_tls", label="Use TLS (rediss)", type="bool", required=False),
    )

    def broker_url(self) -> str:
        scheme = "rediss" if self.config.get("use_tls") else "redis"
        username = self.config.get("username") or ""
        password = self.config.get("password") or ""
        credentials = ""
        if username or password:
            credentials = quote(username, safe="") + ":" + quote(password, safe="") + "@"
        host = self.config["host"]
        port = self.config["port"]
        db = self.config.get("db", 0)
        return f"{scheme}://{credentials}{host}:{port}/{db}"
