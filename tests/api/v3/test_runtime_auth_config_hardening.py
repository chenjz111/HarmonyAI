"""Bounded JWT claim and production-config gates; synthetic data only.

No new token fields, login/logout endpoints, session revocation or migrations.
"""
from datetime import datetime, timedelta, timezone
import json
import pytest
from jose import jwt

from backend.app.core.config import Settings, settings
from backend.app.models.v3.identity import UserIdentity
from tests.api.v3.test_s7_music_library_router_wiring import real_app


def _claims(case):
    with case.factory() as db:
        subject = db.get(UserIdentity, case.owner).public_user_id
    now = int(datetime.now(timezone.utc).timestamp())
    return {'sub': subject, 'auth_type': 'guest', 'iat': now, 'exp': now + 3600}


def _status(case, claims):
    token = jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm='HS256')
    response = case.client.get('/api/v3/me/music-assets', headers={'Authorization': 'Bearer ' + token})
    # Only return the status, so assertion diagnostics never display a token.
    return response.status_code


@pytest.mark.parametrize('claim', ['exp', 'sub', 'iat', 'auth_type'])
def test_each_required_claim_is_mandatory(real_app, claim):
    claims = _claims(real_app)
    del claims[claim]
    assert _status(real_app, claims) == 401


@pytest.mark.parametrize('field,value', [
    ('exp', None), ('exp', True), ('exp', '4102444800'), ('exp', 4102444800.5),
    ('iat', None), ('iat', False), ('iat', '1'), ('iat', 1.5), ('iat', -1),
    ('sub', ''), ('sub', ' '), ('sub', 123), ('sub', []),
    ('auth_type', ''), ('auth_type', 'admin'), ('auth_type', None), ('auth_type', []),
], ids=['exp-null', 'exp-bool', 'exp-string', 'exp-float', 'iat-null', 'iat-bool', 'iat-string', 'iat-float', 'iat-negative', 'sub-empty', 'sub-blank', 'sub-number', 'sub-list', 'type-empty', 'type-unknown', 'type-null', 'type-list'])
def test_claim_format_is_strict(real_app, field, value):
    claims = _claims(real_app)
    claims[field] = value
    assert _status(real_app, claims) == 401


@pytest.mark.parametrize('case', ['future-iat', 'exp-before-iat', 'exp-at-iat', 'expired'])
def test_claim_time_order_and_validity(real_app, case):
    claims = _claims(real_app)
    if case == 'future-iat': claims['iat'] += 600
    elif case == 'exp-before-iat': claims['exp'] = claims['iat'] - 1
    elif case == 'exp-at-iat': claims['exp'] = claims['iat']
    else: claims['iat'], claims['exp'] = 1, 2
    assert _status(real_app, claims) == 401


def test_existing_issued_guest_token_and_claims_still_work(real_app):
    response = real_app.client.get('/api/v3/me/music-assets', headers=real_app.headers)
    assert response.status_code == 200
    token = real_app.headers['Authorization'].split(' ', 1)[1]
    claims = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
    assert set(claims) == {'exp', 'iat', 'sub', 'auth_type'}
    assert claims['auth_type'] == 'guest'
    assert claims['exp'] - claims['iat'] == settings.JWT_EXPIRE_MINUTES * 60
    assert 'sid' not in claims and 'epoch' not in claims


def test_guest_token_cannot_become_registered_authority(real_app):
    with real_app.factory.begin() as db:
        identity = db.get(UserIdentity, real_app.owner)
        identity.auth_type, identity.guest_expires_at = 'registered', None
    status = real_app.client.get('/api/v3/me/music-assets', headers=real_app.headers).status_code
    assert status == 401


def test_claim_auth_type_must_match_current_identity(real_app):
    claims = _claims(real_app)
    claims['auth_type'] = 'registered'
    assert _status(real_app, claims) == 401


@pytest.fixture
def clean_config_env(monkeypatch):
    for key in ['APP_ENV', 'DEBUG', 'JWT_SECRET_KEY', 'JWT_ALGORITHM', 'DATABASE_URL', 'CORS_ORIGINS']:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def _production(monkeypatch, **overrides):
    monkeypatch.setenv('APP_ENV', 'production')
    values = {
        'DEBUG': False,
        'JWT_SECRET_KEY': 'a74d910fb8c530e96d42af035c8e710ed16f75ac2089b46d13cf804eab692f07',
        'DATABASE_URL': 'mysql+pymysql://synthetic:synthetic-password@db.synthetic.invalid:3306/harmonyai',
        'CORS_ORIGINS': ['https://app.synthetic.invalid'],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize('bad', [
    {'DEBUG': True}, {'JWT_SECRET_KEY': ''}, {'JWT_SECRET_KEY': 'change-me-in-production'},
    {'JWT_SECRET_KEY': 'short-synthetic'}, {'JWT_SECRET_KEY': 'a' * 64},
    {'JWT_ALGORITHM': 'HS384'}, {'CORS_ORIGINS': ['*']},
    {'CORS_ORIGINS': ['https://*.synthetic.invalid']}, {'CORS_ORIGINS': ['null']},
    {'CORS_ORIGINS': ['https://app.synthetic.invalid/path']},
    {'CORS_ORIGINS': ['http://app.synthetic.invalid']},
    {'DATABASE_URL': ''}, {'DATABASE_URL': 'sqlite:///relative.sqlite'},
    {'DATABASE_URL': 'sqlite:///:memory:'}, {'DATABASE_URL': 'mysql+pymysql://user:synthetic@db.synthetic.invalid'},
    {'DATABASE_URL': 'mysql+pymysql://user:synthetic@/harmonyai'},
    {'DATABASE_URL': 'mysql+pymysql://db.synthetic.invalid/harmonyai'},
    {'DATABASE_URL': 'postgresql://user:synthetic@db.synthetic.invalid/harmonyai'},
], ids=['debug', 'key-empty', 'key-default', 'key-short', 'key-repeated', 'algorithm', 'cors-star', 'cors-subdomain-star', 'cors-null', 'cors-path', 'cors-http', 'db-empty', 'db-relative', 'db-memory', 'db-name-missing', 'db-host-missing', 'db-user-missing', 'db-unsupported'])
def test_production_rejects_unsafe_config(clean_config_env, bad):
    with pytest.raises(ValueError):
        _production(clean_config_env, **bad)


@pytest.mark.parametrize('missing', ['JWT_SECRET_KEY', 'DATABASE_URL', 'CORS_ORIGINS', 'DEBUG'])
def test_production_missing_required_config_is_rejected(clean_config_env, missing):
    clean_config_env.setenv('APP_ENV', 'production')
    values = dict(DEBUG=False, JWT_SECRET_KEY='a74d910fb8c530e96d42af035c8e710ed16f75ac2089b46d13cf804eab692f07', DATABASE_URL='mysql+pymysql://user:synthetic@db.synthetic.invalid/harmonyai', CORS_ORIGINS=['https://app.synthetic.invalid'])
    values.pop(missing)
    with pytest.raises(ValueError): Settings(_env_file=None, **values)


@pytest.mark.parametrize('mode', ['staging', 'prod', '', 'PRODUCTION'])
def test_unknown_environment_is_not_silently_development(clean_config_env, mode):
    clean_config_env.setenv('APP_ENV', mode)
    with pytest.raises(ValueError): Settings(_env_file=None)


def test_development_defaults_remain_available(clean_config_env):
    conf = Settings(_env_file=None)
    assert conf.DEBUG is True
    assert conf.DATABASE_URL == 'sqlite:///./harmonyai.db'
    assert conf.CORS_ORIGINS == ['*']
    assert getattr(conf, 'APP_ENV', None) == 'development'


def test_development_can_disable_debug_without_claiming_production(clean_config_env):
    conf = Settings(_env_file=None, DEBUG=False)
    assert conf.DEBUG is False
    assert getattr(conf, 'APP_ENV', None) == 'development'


def test_valid_production_config_does_not_connect_database(clean_config_env):
    conf = _production(clean_config_env)
    assert getattr(conf, 'APP_ENV', None) == 'production'
    assert conf.DEBUG is False and conf.JWT_ALGORITHM == 'HS256'


def test_explicit_absolute_sqlite_target_is_unambiguous(clean_config_env, tmp_path):
    target = tmp_path / 'not-created.sqlite'
    conf = _production(clean_config_env, DATABASE_URL='sqlite:///' + str(target), CORS_ORIGINS=[])
    assert conf.DATABASE_URL.startswith('sqlite:///')
    assert not target.exists()  # Config validation must never initialize a DB.


def test_config_errors_and_repr_do_not_disclose_secret_values(clean_config_env):
    marker = 'synthetic-private-value-do-not-log-9f4d1ca0'
    safe = _production(clean_config_env, JWT_SECRET_KEY=marker)
    assert marker not in repr(safe)
    assert 'synthetic-password' not in repr(safe)
    with pytest.raises(ValueError) as error:
        _production(clean_config_env, JWT_SECRET_KEY=marker, DEBUG=True)
    assert marker not in str(error.value)
    assert 'synthetic-password' not in str(error.value)


def test_structured_config_errors_do_not_retain_secret_input(clean_config_env):
    marker = 'synthetic-private-value-do-not-log-9f4d1ca0'
    with pytest.raises(ValueError) as error:
        _production(clean_config_env, JWT_SECRET_KEY=marker, DEBUG=True)
    details = error.value.errors() if hasattr(error.value, 'errors') else error.value.args
    serialized = json.dumps(details, default=str)
    assert marker not in serialized
    assert 'synthetic-password' not in serialized


@pytest.mark.parametrize('query', ['host=other.synthetic.invalid', 'database=', 'user=', 'password=', 'unix_socket=synthetic.sock'])
def test_production_database_query_cannot_override_target(clean_config_env, query):
    target = 'mysql+pymysql://user:synthetic@db.synthetic.invalid/harmonyai?' + query
    with pytest.raises(ValueError):
        _production(clean_config_env, DATABASE_URL=target)
