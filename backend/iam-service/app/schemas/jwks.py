from pydantic import BaseModel


class Jwk(BaseModel):
    kty: str
    use: str
    alg: str
    kid: str
    n: str
    e: str


class JwksResponse(BaseModel):
    keys: list[Jwk]
