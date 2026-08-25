from urllib.parse import quote

from app.providers.base import ProviderField, ProviderSendError
from app.providers.queue.base import QueueProvider


class SqsQueueProvider(QueueProvider):
    """Amazon SQS as the broker, via Kombu's SQS transport.

    Needs boto3 at runtime; it is deliberately NOT in requirements.txt, because it is a
    heavyweight dependency only a tenant on AWS will ever exercise. verify() therefore checks
    for it first and fails with a plain "pip install boto3" message rather than an opaque
    ImportError from deep inside Kombu - a config that cannot possibly work should say so the
    moment it is tested, not on the first invite."""

    key = "sqs"
    label = "Amazon SQS"
    description = "Use Amazon SQS as the message broker. Requires boto3 on the worker host."
    fields: tuple[ProviderField, ...] = (
        ProviderField(name="access_key_id", label="Access key ID", secret=True),
        ProviderField(name="secret_access_key", label="Secret access key", secret=True),
        ProviderField(name="region", label="Region", default="us-east-1", placeholder="us-east-1"),
        ProviderField(
            name="queue_name_prefix",
            label="Queue name prefix",
            required=False,
            help="Prefixed to every queue created in your account, so TalentOS queues are easy to identify.",
        ),
    )

    def broker_url(self) -> str:
        access_key = quote(self.config["access_key_id"], safe="")
        secret_key = quote(self.config["secret_access_key"], safe="")
        return f"sqs://{access_key}:{secret_key}@"

    def transport_options(self) -> dict:
        options: dict = {"region": self.config["region"]}
        if self.config.get("queue_name_prefix"):
            options["queue_name_prefix"] = self.config["queue_name_prefix"]
        return options

    def verify(self) -> str:
        try:
            import boto3  # noqa: F401
        except ImportError as exc:
            raise ProviderSendError("Amazon SQS support needs boto3 on the worker host: pip install boto3") from exc
        return super().verify()
