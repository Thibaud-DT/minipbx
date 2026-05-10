from app.security import hash_password, verify_password


def test_password_hash_roundtrip_uses_internal_pbkdf2_format():
    password_hash = hash_password("long-password")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("long-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_password_verification_accepts_legacy_passlib_pbkdf2_hash():
    legacy_hash = (
        "$pbkdf2-sha256$29000$XAtB6B0jZGztfc95T2ntHQ"
        "$z75XTPQ0jUeH5yJKlO0Arm21x.6JWaK9bUfd14bblHc"
    )

    assert verify_password("long-password", legacy_hash)
    assert not verify_password("wrong-password", legacy_hash)


def test_password_verification_rejects_invalid_hashes():
    assert not verify_password("long-password", "")
    assert not verify_password("long-password", "pbkdf2_sha256$bad")
    assert not verify_password("long-password", "$bcrypt$not-supported")
