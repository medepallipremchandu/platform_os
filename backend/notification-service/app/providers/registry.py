"""The two provider registries, and the one place that knows how to turn a stored
NotificationProviderConfig row back into a live provider instance.

Adding a provider is: write the class, add it to the tuple below. The API's catalog endpoint,
iam-console's generic config form, config validation, secret encryption and the "Test
connection" button all pick it up with no further changes - which is the entire point of
declaring fields on the class instead of hardcoding forms per vendor.
"""
from app.core_crypto import decrypt_secrets
from app.providers.base import Provider, ProviderConfigError
from app.providers.email import ConsoleEmailProvider, EmailProvider, SendGridEmailProvider, SmtpEmailProvider
from app.providers.queue import (
    PostgresQueueProvider,
    QueueProvider,
    RabbitMqQueueProvider,
    RedisQueueProvider,
    SqsQueueProvider,
)

# ConsoleEmailProvider is registered so it shows up in the catalog and can be selected
# deliberately (a staging organization that wants mail suppressed), but it is also what the
# platform falls back to when nothing at all is configured - see app/services/resolver.py.
EMAIL_PROVIDERS: tuple[type[EmailProvider], ...] = (
    SmtpEmailProvider,
    SendGridEmailProvider,
    ConsoleEmailProvider,
)

QUEUE_PROVIDERS: tuple[type[QueueProvider], ...] = (
    PostgresQueueProvider,
    RedisQueueProvider,
    RabbitMqQueueProvider,
    SqsQueueProvider,
)

_BY_KIND: dict[str, dict[str, type[Provider]]] = {
    "email": {cls.key: cls for cls in EMAIL_PROVIDERS},
    "queue": {cls.key: cls for cls in QUEUE_PROVIDERS},
}

PROVIDER_KINDS = tuple(_BY_KIND)


def provider_class(kind: str, key: str) -> type[Provider]:
    by_key = _BY_KIND.get(kind)
    if by_key is None:
        raise ProviderConfigError(f"Unknown provider kind {kind!r} (expected one of {PROVIDER_KINDS})")
    cls = by_key.get(key)
    if cls is None:
        raise ProviderConfigError(f"Unknown {kind} provider {key!r} (expected one of {sorted(by_key)})")
    return cls


def catalog() -> list[dict]:
    """Everything iam-console needs to render a config form for any provider, without the
    console hardcoding a single vendor's field list."""
    return [cls.spec() for by_key in _BY_KIND.values() for cls in by_key.values()]


def split_secrets(kind: str, key: str, submitted: dict) -> tuple[dict, dict]:
    """Partition a submitted config into (plain, secret) by the provider's own declaration.

    Only the keys the provider actually declares are considered - anything else is dropped here
    rather than persisted, so a stray field can never end up stored in the clear just because a
    caller invented it."""
    cls = provider_class(kind, key)
    secret_names = cls.secret_field_names()
    declared = {f.name for f in cls.fields}
    plain = {k: v for k, v in submitted.items() if k in declared and k not in secret_names}
    secret = {k: v for k, v in submitted.items() if k in secret_names and v not in (None, "")}
    return plain, secret


def instantiate(kind: str, key: str, config: dict, secrets_encrypted: str | None) -> Provider:
    """Rebuild a live provider from a stored row: merge the decrypted secrets back over the
    plain config and hand the whole thing to the provider's constructor, which validates it.

    Decryption happens here, at the last possible moment, so plaintext credentials exist only
    inside the worker's own process for the duration of one send."""
    merged = {**config, **decrypt_secrets(secrets_encrypted)}
    return provider_class(kind, key)(merged)
