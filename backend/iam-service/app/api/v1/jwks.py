from fastapi import APIRouter

from app.core.jwt_keys import build_jwks
from app.schemas.jwks import JwksResponse

router = APIRouter(tags=["jwks"])


@router.get("/.well-known/jwks.json", response_model=JwksResponse)
def get_jwks():
    return build_jwks()
