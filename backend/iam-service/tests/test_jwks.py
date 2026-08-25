def test_jwks_shape(client):
    response = client.get("/.well-known/jwks.json")
    assert response.status_code == 200
    body = response.json()
    assert "keys" in body
    assert len(body["keys"]) == 1
    jwk = body["keys"][0]
    assert jwk["kty"] == "RSA"
    assert jwk["use"] == "sig"
    assert jwk["alg"] == "RS256"
    assert "kid" in jwk and jwk["kid"]
    assert "n" in jwk and jwk["n"]
    assert "e" in jwk and jwk["e"]


def test_jwks_requires_no_auth(client):
    # No Authorization header sent at all - must still succeed.
    response = client.get("/.well-known/jwks.json", headers={})
    assert response.status_code == 200
