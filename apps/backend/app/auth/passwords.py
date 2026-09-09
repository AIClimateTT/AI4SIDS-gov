import bcrypt

_DUMMY_HASH: bytes = bcrypt.hashpw(
    b"dummy_placeholder_no_real_user",
    bcrypt.gensalt(),
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_with_timing_protection(plain: str, hashed: str | None) -> bool:
    """Always runs bcrypt so missing users take the same time as real ones."""
    if hashed is None:
        bcrypt.checkpw(plain.encode("utf-8"), _DUMMY_HASH)
        return False
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
