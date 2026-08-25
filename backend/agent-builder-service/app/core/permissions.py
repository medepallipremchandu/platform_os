"""Permission code constants this service checks against the `permissions` claim of a
verified iam-service access token. These strings must match iam-service's seeded catalog
exactly (see iam-service/scripts/seed_permissions_and_roles.py) - they are not derived or
guessed, they are looked up 1:1 against that source of truth.
"""

MODELS_MANAGE = "talentos.agentbuilder.models.manage"
AGENTS_READ = "talentos.agentbuilder.agents.read"
AGENTS_WRITE = "talentos.agentbuilder.agents.write"
AGENTS_PUBLISH = "talentos.agentbuilder.agents.publish"
AGENTS_MANAGE_KEYS = "talentos.agentbuilder.agents.manage_keys"

# This service's own machine identity uses this permission to manage service principals in
# iam-service on behalf of publish/regenerate - never checked against an end user's token.
IAM_SERVICE_PRINCIPALS_MANAGE = "talentos.iam.service_principals.manage"
