from fastapi import APIRouter

from app.api.v1 import audit, auth, jwks, organizations, permissions, role_assignments, role_definitions, service_principals

router = APIRouter()

# Every path here is mounted at the service root (no /api/v1 prefix) - other services and
# iam-console depend on these exact paths (see design doc §9), e.g. POST /auth/login,
# GET /.well-known/jwks.json.
router.include_router(jwks.router)
router.include_router(auth.router)
router.include_router(organizations.router)
router.include_router(role_definitions.router)
router.include_router(role_assignments.router)
router.include_router(service_principals.router)
router.include_router(audit.router)
router.include_router(permissions.router)
