"""Argon2id password hashing with safe verification behavior."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class Passwords:
    def __init__(self):
        self._hasher = PasswordHasher()
        self._dummy_hash = self._hasher.hash("not-a-real-account-password-4938")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, encoded: str, password: str) -> bool:
        try:
            return self._hasher.verify(encoded, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def needs_rehash(self, encoded: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(encoded)
        except InvalidHashError:
            return False

    def verify_or_dummy(self, encoded: str | None, password: str) -> bool:
        """Run Argon2 even for an unknown account to reduce timing-based enumeration."""
        return self.verify(encoded or self._dummy_hash, password)
