"""The provider abstraction itself: field validation, secret partitioning, encryption at rest,
and the broker URLs each queue provider builds."""
import pytest

from app.core_crypto import decrypt_secrets, encrypt_secrets
from app.providers.base import ProviderConfigError
from app.providers.email import SmtpEmailProvider
from app.providers.queue import PostgresQueueProvider, RabbitMqQueueProvider, RedisQueueProvider, SqsQueueProvider
from app.providers.registry import catalog, instantiate, provider_class, split_secrets


def test_catalog_exposes_every_provider_with_its_fields():
    specs = catalog()
    keys = {(spec["kind"], spec["key"]) for spec in specs}
    assert ("email", "smtp") in keys
    assert ("email", "sendgrid") in keys
    assert ("queue", "redis") in keys
    assert ("queue", "rabbitmq") in keys
    smtp = next(spec for spec in specs if spec["key"] == "smtp")
    assert {f["name"] for f in smtp["fields"]} >= {"host", "port", "password", "from_address"}
    assert next(f for f in smtp["fields"] if f["name"] == "password")["secret"] is True


def test_missing_required_field_is_a_config_error_not_a_crash():
    with pytest.raises(ProviderConfigError) as exc:
        SmtpEmailProvider({"port": 587})
    assert "host" in str(exc.value).lower()


def test_defaults_are_applied_and_types_coerced():
    provider = SmtpEmailProvider({"host": "smtp.example.com", "port": "2525", "from_address": "a@b.com"})
    assert provider.config["port"] == 2525
    assert provider.config["use_tls"] is True  # declared default


def test_split_secrets_partitions_by_the_providers_own_declaration():
    plain, secrets = split_secrets(
        "email",
        "smtp",
        {"host": "smtp.example.com", "port": 587, "from_address": "a@b.com", "password": "hunter2", "bogus": "x"},
    )
    assert secrets == {"password": "hunter2"}
    assert "password" not in plain
    # An undeclared key is dropped rather than persisted in the clear.
    assert "bogus" not in plain


def test_secrets_round_trip_through_fernet_and_are_not_readable_as_plaintext():
    blob = encrypt_secrets({"password": "hunter2"})
    assert blob is not None and "hunter2" not in blob
    assert decrypt_secrets(blob) == {"password": "hunter2"}


def test_empty_secrets_encrypt_to_null_rather_than_an_encrypted_empty_object():
    assert encrypt_secrets({}) is None
    assert decrypt_secrets(None) == {}


def test_instantiate_merges_decrypted_secrets_back_over_the_stored_config():
    blob = encrypt_secrets({"password": "hunter2"})
    provider = instantiate("email", "smtp", {"host": "h", "port": 25, "from_address": "a@b.com"}, blob)
    assert provider.config["password"] == "hunter2"


def test_unknown_provider_is_rejected_by_name():
    with pytest.raises(ProviderConfigError):
        provider_class("email", "carrier-pigeon")
    with pytest.raises(ProviderConfigError):
        provider_class("telepathy", "smtp")


def test_postgres_queue_url_uses_the_kombu_sqla_scheme_not_sqlalchemys():
    url = PostgresQueueProvider(
        {"host": "localhost", "port": 5432, "database": "db", "username": "u", "password": "p@ss"}
    ).broker_url()
    assert url.startswith("sqla+postgresql://")
    # The credential is percent-encoded, so an "@" in a password cannot split the authority.
    assert "p%40ss" in url
    assert url.endswith("@localhost:5432/db")


def test_redis_queue_url_switches_scheme_for_tls():
    plain = RedisQueueProvider({"host": "h", "port": 6379, "db": 1}).broker_url()
    assert plain == "redis://h:6379/1"
    tls = RedisQueueProvider({"host": "h", "port": 6379, "db": 0, "use_tls": True}).broker_url()
    assert tls.startswith("rediss://")


def test_rabbitmq_default_vhost_is_an_empty_path():
    default_vhost = RabbitMqQueueProvider({"host": "h", "port": 5672, "username": "u", "password": "p"}).broker_url()
    assert default_vhost.endswith(":5672/")
    named = RabbitMqQueueProvider(
        {"host": "h", "port": 5672, "username": "u", "password": "p", "vhost": "/prod"}
    ).broker_url()
    assert named.endswith("/%2Fprod")


def test_sqs_puts_the_region_in_transport_options_not_the_url():
    provider = SqsQueueProvider({"access_key_id": "AKIA", "secret_access_key": "s3cret", "region": "eu-west-1"})
    assert provider.broker_url() == "sqs://AKIA:s3cret@"
    assert provider.transport_options()["region"] == "eu-west-1"


def test_a_tenant_app_publishes_to_the_tenant_broker_not_the_platform_one(monkeypatch):
    """Regression, and the nastiest bug in this service's history.

    celery.app.utils.Settings.broker_url reads os.environ["CELERY_BROKER_URL"] FIRST, ahead of
    anything the application configures - and Celery treats the Celery(broker=...) constructor
    argument as merely "auto-set", so it loses to that too. While this service's own setting was
    named CELERY_BROKER_URL, every tenant Celery app came up silently pointed at the PLATFORM
    broker: mail was still delivered, nothing errored, the console still said "your Redis", and
    the tenant's queue was simply never used.

    The env var is set here deliberately - that is the exact condition that broke it."""
    from app.celery_app import build_celery_app

    monkeypatch.setenv("CELERY_BROKER_URL", "sqla+postgresql://postgres:postgres@localhost:5432/platform_broker")
    tenant_url = "redis://tenant.example.com:6379/0"
    app = build_celery_app("tenant-under-test", tenant_url, set_as_current=False)
    assert app.conf.broker_url == tenant_url
