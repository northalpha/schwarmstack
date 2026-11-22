from submissions.tokens import hash_ip, hash_token, new_token, token_matches


def test_token_hat_32_byte_zufall():
    token = new_token()
    assert len(token) >= 43  # 32 Byte, base64url
    assert new_token() != token


def test_nur_der_hash_passt():
    token = new_token()
    stored = hash_token(token)
    assert len(stored) == 64 and token not in stored
    assert token_matches(token, stored)
    assert not token_matches(token + "x", stored)


def test_pfeffer_aendert_den_hash(settings):
    settings.TOKEN_PEPPER = "a"  # noqa: S105
    first = hash_token("x")
    settings.TOKEN_PEPPER = "b"  # noqa: S105
    assert hash_token("x") != first


def test_ip_hash_ist_nicht_die_ip():
    value = hash_ip("203.0.113.7")
    assert "203" not in value and len(value) == 64
    assert hash_ip("203.0.113.7") == value
    assert hash_ip("203.0.113.8") != value
