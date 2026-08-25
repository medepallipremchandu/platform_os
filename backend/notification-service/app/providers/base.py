"""The provider contract shared by both plug-in axes of this service.

Two independent registries hang off this module:

  * email providers  - HOW an organization's transactional mail physically leaves the platform
                       (SMTP, SendGrid, or the console sink used when nothing is configured)
  * queue providers  - WHICH broker an organization's notifications are dispatched onto
                       (Postgres, Redis, RabbitMQ, SQS)

They share one base class because everything around them is identical: a declared field spec
that both validates a tenant's submitted config and drives a generic form in iam-console, a
declaration of which fields are secret (so the service layer knows what to encrypt and what to
never return), and a `verify()` used by the "Test connection" endpoint. Adding a provider is
one new module plus one registry entry - no changes to the API, the models, or the UI.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ProviderConfigError(ValueError):
    """A tenant-supplied config is missing a required field, has the wrong type, or names an
    unknown provider. Surfaces as a 400, never a 500."""


class ProviderSendError(RuntimeError):
    """The provider was configured correctly but the remote end refused or was unreachable.
    Retryable - app.tasks lets Celery back off and try again."""


@dataclass(frozen=True)
class ProviderField:
    """One configurable field of a provider. `secret=True` means the value is Fernet-encrypted
    at rest and never included in an API response - only ever written."""

    name: str
    label: str
    type: str = "string"  # "string" | "int" | "bool" | "email" | "text"
    required: bool = True
    secret: bool = False
    default: Any = None
    help: str | None = None
    placeholder: str | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "secret": self.secret,
            "default": self.default,
            "help": self.help,
            "placeholder": self.placeholder,
        }


class Provider(ABC):
    kind: str = ""
    key: str = ""
    label: str = ""
    description: str = ""
    fields: tuple[ProviderField, ...] = ()

    def __init__(self, config: dict[str, Any]):
        self.config = validate_against_fields(self.fields, config, provider_label=self.label)

    @classmethod
    def spec(cls) -> dict:
        return {
            "kind": cls.kind,
            "key": cls.key,
            "label": cls.label,
            "description": cls.description,
            "fields": [f.as_dict() for f in cls.fields],
        }

    @classmethod
    def secret_field_names(cls) -> set[str]:
        return {f.name for f in cls.fields if f.secret}

    @abstractmethod
    def verify(self) -> str:
        """Prove the config actually works against the remote end. Returns a short human-readable
        success message; raises ProviderSendError (or ProviderConfigError) otherwise. Backs the
        "Test connection" button, so it must be cheap and side-effect-light."""


def _coerce(f: ProviderField, raw: Any) -> Any:
    if f.type == "int":
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ProviderConfigError(f"'{f.label}' must be a whole number")
    if f.type == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        return bool(raw)
    return str(raw).strip() if raw is not None else raw


def validate_against_fields(fields: tuple[ProviderField, ...], config: dict, *, provider_label: str) -> dict[str, Any]:
    """Coerce and check a submitted config against a provider's declared fields. Unknown keys are
    dropped rather than rejected: a tenant re-submitting an older form (or a provider that has
    since lost a field) should not hard-fail, and silently ignoring an extra key is strictly safer
    than persisting something no provider will ever read."""
    known = {f.name: f for f in fields}
    resolved: dict[str, Any] = {}
    for name, f in known.items():
        if name in config and config[name] not in (None, ""):
            resolved[name] = _coerce(f, config[name])
        elif f.default is not None:
            resolved[name] = f.default
        elif f.type == "bool":
            resolved[name] = False
        elif f.required:
            raise ProviderConfigError(f"{provider_label}: '{f.label}' is required")
    return resolved
