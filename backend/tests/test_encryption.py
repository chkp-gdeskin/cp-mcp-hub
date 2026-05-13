from app.core.encryption import decrypt, encrypt


def test_encryption_roundtrip():
    plaintext = "very-secret-api-key-12345"
    ct = encrypt(plaintext)
    assert ct != plaintext
    assert decrypt(ct) == plaintext


def test_encryption_distinct_outputs():
    a = encrypt("same")
    b = encrypt("same")
    assert a != b  # Fernet includes IV
    assert decrypt(a) == decrypt(b) == "same"
