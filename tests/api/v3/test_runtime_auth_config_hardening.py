"""Bounded JWT claim and production-config gates; synthetic data only.

No new token fields, login/logout endpoints, session revocation or migrations.
"""
from datetime import datetime, timedelta, timezone
import json
import ssl
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
def synthetic_ca(tmp_path):
    # Locally generated public CA only; no private key is written or reused.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic offline CA')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    path = tmp_path / 'synthetic-ca.pem'
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return path


@pytest.fixture
def clean_config_env(monkeypatch, synthetic_ca):
    for key in ['APP_ENV', 'DEBUG', 'JWT_SECRET_KEY', 'JWT_ALGORITHM', 'DATABASE_URL', 'CORS_ORIGINS', 'MYSQL_TLS_CA_FILE']:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('MYSQL_TLS_CA_FILE', str(synthetic_ca))
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


@pytest.mark.parametrize('key', [
    '0123456789abcdef' * 4,
    ('0123456789abcdef' * 4) + '012',
    'fE7!aQ2@rT9#uI4$' * 2,
    'fedcba9876543210' * 4,
    'abcdefghijklmnopqrstuvwxyz0123456789',
    '9876543210zyxwvutsrqponmlkjihgfedcba',
    '0123456789abcdefghijklmnopqrstuvwxyz',
    'qwertyuiopasdfghjklzxcvbnm0123456789',
], ids=['hex-period', 'truncated-period', 'mixed-block', 'reverse-period',
        'alphabet-sequence', 'reverse-sequence', 'digit-sequence', 'keyboard-sequence'])
def test_production_rejects_obvious_predictable_keys(clean_config_env, key):
    # These synthetic inputs pass the old length/distinct-character screens.
    # Removing the predictable-pattern gate must make these tests fail.
    with pytest.raises(ValueError) as error:
        _production(clean_config_env, JWT_SECRET_KEY=key)
    assert key not in str(error.value)
    assert key not in repr(error.value.args)


@pytest.mark.parametrize('key', [
    'a74d910fb8c530e96d42af035c8e710ed16f75ac2089b46d13cf804eab692f07',
    'V7!mQ2@zL9#bR4$xN8%wC3^pH6&kD1*s',
    'synthetic-prefix-0123456789abcdef-0123456789abcdef-tail',
])
def test_production_pattern_screen_accepts_nonperiodic_synthetic_keys(clean_config_env, key):
    # Acceptance is configuration compatibility, not proof of key entropy.
    conf = _production(clean_config_env, JWT_SECRET_KEY=key)
    assert conf.JWT_SECRET_KEY == key


def test_development_periodic_key_compatibility_is_unchanged(clean_config_env):
    conf = Settings(_env_file=None, JWT_SECRET_KEY='0123456789abcdef' * 4)
    assert conf.APP_ENV == 'development'


@pytest.mark.parametrize('query', [
    'charset=utf8mb4', 'connect_timeout=1', 'read_timeout=600', 'write_timeout=30',
    'charset=utf8mb4&connect_timeout=10&read_timeout=20&write_timeout=30',
])
def test_mysql_approved_parameters_are_accepted(clean_config_env, query):
    conf = _production(clean_config_env, DATABASE_URL='mysql+pymysql://user:synthetic@db.synthetic.invalid/harmonyai?' + query)
    assert conf.APP_ENV == 'production'


@pytest.mark.parametrize('query', [
    'charset=utf8', 'charset=', 'charset=utf8mb4&charset=utf8mb4',
    'connect_timeout=0', 'connect_timeout=601', 'read_timeout=-1',
    'write_timeout=1.5', 'read_timeout=true', 'write_timeout=',
    'read_timeout=1&read_timeout=2', 'unknown=1', 'host=other.invalid',
    'db=other', 'database=other', 'user=other', 'passwd=other',
    'port=1', 'unix_socket=other', 'ssl_disabled=true', 'ssl_check_hostname=false',
    'ssl_ca=other', 'local_infile=true', 'init_command=SELECT+1',
    'read_timeout=1&password=', 'read_timeout=1&broken',
])
def test_mysql_unapproved_parameters_are_rejected(clean_config_env, query):
    with pytest.raises(ValueError):
        _production(clean_config_env, DATABASE_URL='mysql+pymysql://user:synthetic@db.synthetic.invalid/harmonyai?' + query)


@pytest.mark.parametrize('driver', ['mysql', 'mysql+mysqldb', 'mysql+mysqlconnector'])
def test_production_mysql_requires_explicit_pymysql(clean_config_env, driver):
    with pytest.raises(ValueError):
        _production(clean_config_env, DATABASE_URL=driver + '://user:synthetic@db.synthetic.invalid/harmonyai')


@pytest.mark.parametrize('case', ['missing', 'blank', 'nonexistent', 'directory', 'invalid-pem', 'relative'])
def test_production_mysql_invalid_ca_is_rejected(clean_config_env, tmp_path, case):
    clean_config_env.delenv('MYSQL_TLS_CA_FILE')
    if case == 'missing':
        values = {}
    else:
        invalid = tmp_path / 'invalid.pem'
        invalid.write_text('not a CA certificate', encoding='utf-8')
        values = {'MYSQL_TLS_CA_FILE': {
            'blank': '', 'nonexistent': str(tmp_path/'absent.pem'),
            'directory': str(tmp_path), 'invalid-pem': str(invalid),
            'relative': 'relative-ca.pem',
        }[case]}
    with pytest.raises(ValueError) as error:
        _production(clean_config_env, **values)
    assert 'synthetic-password' not in str(error.value)


def test_tls_context_failure_is_redacted_and_never_falls_back(clean_config_env):
    def unavailable(*args, **kwargs):
        raise OSError('synthetic-private-tls-error')
    clean_config_env.setattr(ssl, 'create_default_context', unavailable)
    with pytest.raises(ValueError) as error:
        _production(clean_config_env)
    assert 'synthetic-private-tls-error' not in str(error.value)


def test_actual_engine_parameters_and_pymysql_context(clean_config_env):
    from sqlalchemy import event
    from backend.app.core import database
    from pymysql import Connection
    conf = _production(clean_config_env, DATABASE_URL='mysql+pymysql://user:synthetic@db.synthetic.invalid:3306/harmonyai?charset=utf8mb4&connect_timeout=10&read_timeout=20&write_timeout=30')
    engine = database.build_database_engine(conf)
    captured = {}
    class StopBeforeNetwork(Exception):
        pass
    def capture(dialect, connection_record, args, kwargs):
        captured.update(kwargs)
        raise StopBeforeNetwork()
    event.listen(engine, 'do_connect', capture)
    try:
        with pytest.raises(StopBeforeNetwork):
            engine.raw_connection()
        assert captured['host'] == 'db.synthetic.invalid'
        assert captured['database'] == 'harmonyai'
        assert captured['port'] == 3306
        assert captured['charset'] == 'utf8mb4'
        assert [captured[k] for k in ('connect_timeout', 'read_timeout', 'write_timeout')] == [10, 20, 30]
        ctx = captured['ssl']
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True
        assert ctx.cert_store_stats()['x509_ca'] >= 1
        # Actual installed driver consumes the context, without opening a socket.
        driver = Connection(defer_connect=True, **captured)
        assert driver.ctx is ctx and driver.ssl is True
    finally:
        engine.dispose()


def test_engine_rechecks_ca_disappearance_without_plaintext_fallback(clean_config_env, synthetic_ca):
    from backend.app.core import database
    conf = _production(clean_config_env)
    synthetic_ca.unlink()  # Only this test's generated public certificate.
    with pytest.raises(ValueError):
        database.build_database_engine(conf)


def test_sqlite_engine_path_still_works_without_ca(clean_config_env):
    from backend.app.core import database
    from sqlalchemy import text
    clean_config_env.delenv('MYSQL_TLS_CA_FILE')
    conf = Settings(_env_file=None, DATABASE_URL='sqlite:///:memory:')
    engine = database.build_database_engine(conf)
    try:
        with engine.connect() as connection:
            assert connection.execute(text('SELECT 1')).scalar_one() == 1
    finally:
        engine.dispose()
