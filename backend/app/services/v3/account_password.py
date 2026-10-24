"""Owner R1 password operations. Production must supply a reviewed blocklist."""
import re
import unicodedata
from argon2 import PasswordHasher,Type,extract_parameters
from argon2.exceptions import VerificationError,InvalidHashError


def normalize_username(value):
    if not isinstance(value,str) or re.fullmatch(r'[A-Za-z0-9_]{3,32}',value,flags=re.ASCII) is None:
        raise ValueError('invalid username')
    return value.lower()


def normalize_password(value):
    if not isinstance(value,str):raise ValueError('invalid password')
    normalized=unicodedata.normalize('NFC',value)
    if not 15 <= len(normalized) <= 1024:raise ValueError('password length outside approved bounds')
    return normalized


class PasswordPolicy:
    def __init__(self,*,blocked_passwords):
        if not blocked_passwords or any(not isinstance(p,str) or not p for p in blocked_passwords):
            raise ValueError('reviewed common/compromised password blocklist required')
        self._blocked=frozenset(unicodedata.normalize('NFC',p).casefold() for p in blocked_passwords)
        self._hasher=PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1,salt_len=16,hash_len=32,type=Type.ID)

    def validate(self,password):
        normalized=normalize_password(password)
        if normalized.casefold() in self._blocked:raise ValueError('password is disallowed')
        return normalized

    def hash(self,password):
        return self._hasher.hash(self.validate(password))

    def verify(self,encoded,password):
        try:
            normalized=normalize_password(password)
            p=extract_parameters(encoded)
            # Refuse unreviewed hash resource costs instead of unbounded allocation.
            if (p.type,p.version,p.memory_cost,p.time_cost,p.parallelism,p.salt_len,p.hash_len) != (Type.ID,19,19456,2,1,16,32):return False
            return self._hasher.verify(encoded,normalized)
        except (VerificationError,InvalidHashError,ValueError,TypeError):
            return False
