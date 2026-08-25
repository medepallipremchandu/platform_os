"""Small fixed domain constants - not operational config, so not env-driven.

The platform's known set of services is a closed, rarely-changing list baked into the
domain model itself (it drives `scope_id` construction for service-scoped RoleAssignments,
e.g. "<organization_id>:agent-builder"). Adding a new platform service is a code change
(new relying-party service), not a runtime configuration change.
"""
from enum import Enum


class ServiceName(str, Enum):
    IAM = "iam"
    TALENTOS_APP = "talentos-app"
    AGENT_BUILDER = "agent-builder"
    VOICE_AGENT = "voice-agent"


class PrincipalType(str, Enum):
    USER = "user"
    SERVICE_PRINCIPAL = "service_principal"
    # Reserved for a future Groups feature (explicitly deferred, see design doc). Not
    # implemented: no code path creates a RoleAssignment with this value today.
    GROUP = "group"


class ScopeType(str, Enum):
    ORGANIZATION = "organization"
    SERVICE = "service"


class ActorType(str, Enum):
    USER = "user"
    SERVICE_PRINCIPAL = "service_principal"
    SYSTEM = "system"


class AuditResult(str, Enum):
    SUCCESS = "success"
    DENIED = "denied"
    ERROR = "error"


class UserStatus(str, Enum):
    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


def build_service_scope_id(organization_id, service_name: str) -> str:
    return f"{organization_id}:{service_name}"
