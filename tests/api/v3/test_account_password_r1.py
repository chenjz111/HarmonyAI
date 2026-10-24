"""R1 password policy: no network, plaintext logging or production credential."""
import unicodedata
import pytest


def policy():
    from backend.app.services.v3.account_password import PasswordPolicy
    return PasswordPolicy(blocked_passwords={'passwordpassword','known-compromised-long-passphrase'})


@pytest.mark.parametrize('username,expected',[('Alice_123','alice_123'),('abc','abc'),('A'*32,'a'*32)])
def test_ascii_username_normalization(username,expected):
    from backend.app.services.v3.account_password import normalize_username
    assert normalize_username(username) == expected


@pytest.mark.parametrize('username',['ab','a'*33,' abc','abc ','a-b','abc中','ＡＢＣ','user@example'])
def test_username_invalid_is_not_silently_repaired(username):
    from backend.app.services.v3.account_password import normalize_username
    with pytest.raises(ValueError):normalize_username(username)


def test_password_nfc_independent_salts_and_approved_parameters():
    from argon2 import extract_parameters,Type
    p=policy();password='synthetic-cafe'+chr(0x301)+'-long-passphrase'
    first=p.hash(password);second=p.hash(password)
    assert first != second and password not in first
    parameters=extract_parameters(first)
    assert (parameters.type,parameters.memory_cost,parameters.time_cost,parameters.parallelism,parameters.salt_len,parameters.hash_len) == (Type.ID,19456,2,1,16,32)
    assert p.verify(first,unicodedata.normalize('NFC',password))
    assert not p.verify(first,'different-synthetic-long-passphrase')
    assert not p.verify('malformed',password)


@pytest.mark.parametrize('password',['short','passwordpassword','KNOWN-COMPROMISED-LONG-PASSPHRASE'])
def test_short_common_compromised_password_rejected(password):
    with pytest.raises(ValueError): policy().hash(password)


def test_password_long_unicode_is_not_truncated_or_forced_into_categories():
    password='测试合成的密码短语'*10
    p=policy();hashed=p.hash(password)
    assert p.verify(hashed,password) and not p.verify(hashed,password[:-1])


def test_missing_reviewed_blocklist_fails_closed():
    from backend.app.services.v3.account_password import PasswordPolicy
    with pytest.raises(ValueError):PasswordPolicy(blocked_passwords=set())
