"""Opt-in real MySQL acceptance. Creates/stops its OWN new loopback instance.

Never reads default MySQL config, existing data directories, credentials or
services. No downloads. Private TLS keys and disposable data stay outside Git.
This is deliberately separate from the unchanged offline pytest Guard.
"""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]


def certificates(folder):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    folder.mkdir()
    ca_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    now=datetime.now(timezone.utc)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'HarmonyAI disposable MySQL CA')])
    ca=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(ca_key,hashes.SHA256()))
    server=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1')),x509.DNSName('localhost')]),critical=False).sign(ca_key,hashes.SHA256()))
    (folder/'ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (folder/'server.pem').write_bytes(server.public_bytes(serialization.Encoding.PEM))
    (folder/'server-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    return ssl.create_default_context(cafile=str(folder/'ca.pem'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mysqld',required=True,type=Path)
    parser.add_argument('--evidence-dir',required=True,type=Path)
    args=parser.parse_args()
    binary=args.mysqld.resolve(strict=True);out=args.evidence_dir.resolve()
    if binary.name.lower()!='mysqld.exe' or out.exists() or out.is_relative_to(ROOT) or ROOT.is_relative_to(out):parser.error('existing vendor mysqld and NEW external evidence directory required')
    out.mkdir(parents=True)
    data=out/'data';data.mkdir()
    tls=out/'private-tls';context=certificates(tls)
    # Tighten only the newly created private test folder, never a user directory.
    if os.name=='nt':
        import getpass
        subprocess.run(['icacls',str(tls),'/inheritance:r','/grant:r',getpass.getuser()+':(OI)(CI)F','SYSTEM:(OI)(CI)F'],capture_output=True,check=True)
    keep={'PATH','SYSTEMROOT','WINDIR','PATHEXT','TEMP','TMP'}
    clean={k:v for k,v in os.environ.items() if k.upper() in keep}
    version=subprocess.run([str(binary),'--no-defaults','--version'],env=clean,capture_output=True,text=True,check=True).stdout.strip()
    initialized=subprocess.run([str(binary),'--no-defaults','--initialize-insecure','--basedir='+str(binary.parent.parent),'--datadir='+str(data),'--console'],env=clean,capture_output=True,text=True,timeout=90)
    (out/'initialize.log').write_text(initialized.stdout+initialized.stderr,encoding='utf-8')
    if initialized.returncode:raise RuntimeError('isolated initialize failed; inspect local evidence')
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    command=[str(binary),'--no-defaults','--basedir='+str(binary.parent.parent),'--datadir='+str(data),'--bind-address=127.0.0.1','--port='+str(port),'--mysqlx=OFF','--skip-log-bin','--local-infile=OFF','--secure-file-priv=NULL','--require-secure-transport=ON','--ssl-ca='+str(tls/'ca.pem'),'--ssl-cert='+str(tls/'server.pem'),'--ssl-key='+str(tls/'server-key.pem'),'--console']
    checks={};failures=[];server=None;engines=[];phase='server_start'
    log=(out/'server.log').open('w',encoding='utf-8')
    try:
        server=subprocess.Popen(command,env=clean,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        # No other connection or child process can be opened by application code.
        def audit(event,values):
            if event=='socket.connect' and values[1]!=('127.0.0.1',port):raise RuntimeError('isolated MySQL network boundary')
            if event=='socket.getaddrinfo' and values[0]!='127.0.0.1':raise RuntimeError('isolated MySQL DNS boundary')
            if event=='subprocess.Popen':raise RuntimeError('isolated MySQL process boundary')
        sys.addaudithook(audit)
        import pymysql
        root=None;deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if server.poll() is not None:raise RuntimeError('new isolated server exited')
            try:root=pymysql.connect(host='127.0.0.1',port=port,user='root',ssl=context,autocommit=True,connect_timeout=1);break
            except pymysql.OperationalError:time.sleep(.2)
        if root is None:raise RuntimeError('new isolated server readiness timeout')
        with root.cursor() as cursor:
            cursor.execute('SELECT @@datadir,@@server_uuid');directory,server_uuid=cursor.fetchone()
            assert Path(directory).resolve()==data.resolve()
            assert server_uuid in (data/'auto.cnf').read_text()
            cursor.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'");assert cursor.fetchone()[1]
            checks['verified_tls_and_own_instance']=True
            cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s",(secrets.token_urlsafe(32),))
            password=secrets.token_urlsafe(32)
            cursor.execute("CREATE USER 's7_acceptance'@'127.0.0.1' IDENTIFIED BY %s REQUIRE SSL",(password,))
            names={name:'s7_'+name+'_'+uuid4().hex[:12] for name in ['fresh','upgrade','partial','failure']}
            for name in names.values():
                cursor.execute('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
                cursor.execute('GRANT ALL PRIVILEGES ON `'+name+"`.* TO 's7_acceptance'@'127.0.0.1'")
        root.close()
        os.environ.clear();os.environ.update(clean)
        os.environ.update(APP_ENV='development',DEBUG='false',DATABASE_URL='sqlite:///'+str(out/'unused.sqlite'),JWT_SECRET_KEY='isolated-test-key-0123456789-0123456789',MUSIC_PROVIDER='not-configured',PYTHONDONTWRITEBYTECODE='1')
        sys.path.insert(0,str(ROOT))
        from sqlalchemy import create_engine,inspect,text
        from sqlalchemy.engine import URL
        from backend.app.core import database,v3_migrations as migrations
        from backend.app import models  # registers the actual production ORM
        def engine_for(name):
            engine=create_engine(URL.create('mysql+pymysql',username='s7_acceptance',password=password,host='127.0.0.1',port=port,database=names[name]),connect_args={'ssl':context},pool_pre_ping=True)
            engines.append(engine);return engine
        def startup(engine):
            original=database.engine
            try:database.engine=engine;database.init_database()
            finally:database.engine=original
        phase='fresh_create_repeat'
        fresh=engine_for('fresh');startup(fresh);startup(fresh)
        with fresh.connect() as connection:
            assert connection.exec_driver_sql('SELECT COUNT(*) FROM schema_migrations').scalar_one()==14
        checks[phase]=True

        phase='legacy_0001_0012_upgrade'
        versions=migrations.V3_MIGRATION_VERSIONS
        def legacy(engine):
            with engine.begin() as connection:
                connection.exec_driver_sql('CREATE TABLE users(id INTEGER PRIMARY KEY AUTO_INCREMENT,openid VARCHAR(128) NOT NULL UNIQUE,nickname VARCHAR(64),avatar_url TEXT,phone VARCHAR(20),preferred_instruments TEXT,preferred_bpm_min INTEGER,preferred_bpm_max INTEGER,preferred_session VARCHAR(32),effective_syndrome_data TEXT,created_at DATETIME,updated_at DATETIME) ENGINE=InnoDB')
                connection.exec_driver_sql('CREATE TABLE sessions(id INTEGER PRIMARY KEY AUTO_INCREMENT,user_id INTEGER NOT NULL,session_id VARCHAR(64) NOT NULL UNIQUE,status VARCHAR(16),current_agent VARCHAR(32),metadata_json TEXT,created_at DATETIME,updated_at DATETIME) ENGINE=InnoDB')
                connection.exec_driver_sql("CREATE TABLE documents(id INTEGER PRIMARY KEY AUTO_INCREMENT,user_id INTEGER NOT NULL,session_id VARCHAR(64) NOT NULL,document_id VARCHAR(64) NOT NULL UNIQUE,original_filename VARCHAR(256) NOT NULL,file_type VARCHAR(16) NOT NULL,file_size_bytes INTEGER NOT NULL,storage_path VARCHAR(512) NOT NULL,status VARCHAR(16) DEFAULT 'uploaded',created_at DATETIME,updated_at DATETIME) ENGINE=InnoDB")
                connection.exec_driver_sql("INSERT INTO sessions(user_id,session_id,status) VALUES(7,'sess_legacy','active')")
            try:
                migrations.V3_MIGRATION_VERSIONS=versions[:12]
                migrations.apply_v3_migrations(engine)
            finally:migrations.V3_MIGRATION_VERSIONS=versions
        upgrade=engine_for('upgrade');legacy(upgrade)
        with upgrade.connect() as connection:before=connection.exec_driver_sql('SELECT version,checksum FROM schema_migrations ORDER BY version').fetchall()
        result=migrations.apply_v3_migrations(upgrade)
        assert result['applied_versions']==versions[12:]
        assert migrations.apply_v3_migrations(upgrade)['applied_versions']==[]
        with upgrade.connect() as connection:
            assert connection.exec_driver_sql('SELECT version,checksum FROM schema_migrations ORDER BY version').fetchall()[:12]==before
        checks[phase]=True
        phase='ddl_failure_stays_unregistered_and_refuses_restart'
        failed=engine_for('failure');legacy(failed)
        from sqlalchemy import event
        def interrupt(connection,cursor,statement,parameters,context,executemany):
            if statement.startswith('CREATE TRIGGER int2_0013_feedback_immutable'):
                raise RuntimeError('synthetic interruption after additive MySQL DDL')
        event.listen(failed,'before_cursor_execute',interrupt)
        try:
            try:migrations.apply_v3_migrations(failed)
            except RuntimeError as error:assert str(error)=='synthetic interruption after additive MySQL DDL'
            else:raise AssertionError('injected DDL interruption did not occur')
        finally:event.remove(failed,'before_cursor_execute',interrupt)
        with failed.connect() as connection:
            assert connection.exec_driver_sql('SELECT version,checksum FROM schema_migrations ORDER BY version').fetchall()==before
        schema_before={table:tuple(c['name'] for c in inspect(failed).get_columns(table)) for table in inspect(failed).get_table_names()}
        try:migrations.apply_v3_migrations(failed)
        except migrations.MigrationSchemaMismatch:pass
        else:raise AssertionError('partial DDL was automatically adopted')
        assert {table:tuple(c['name'] for c in inspect(failed).get_columns(table)) for table in inspect(failed).get_table_names()}==schema_before
        checks[phase]=True

        phase='partial_schema_refuses_repair'
        partial=engine_for('partial');startup(partial)
        with partial.begin() as connection:connection.exec_driver_sql('DROP TABLE auth_refresh_proofs')
        tables=set(inspect(partial).get_table_names())
        try:startup(partial)
        except migrations.MigrationSchemaMismatch:pass
        else:raise AssertionError('partial schema accepted')
        assert set(inspect(partial).get_table_names())==tables
        checks[phase]=True
        phase='actual_account_feedback_transactions'
        from tools.ci.mysql_runtime_scenarios import verify
        checks[phase]=verify(upgrade)
    except Exception as error:
        failures.append({'phase':phase,'type':type(error).__name__,'code':error.args[0] if error.args and isinstance(error.args[0],int) else None})
        # Diagnostics are local synthetic DDL only; never print connection URIs.
        import traceback
        detail=traceback.format_exc()
        if 'password' in locals():detail=detail.replace(password,'[REDACTED]')
        (out/'failure.log').write_text(detail,encoding='utf-8')
        if engines:
            try:
                from sqlalchemy import inspect
                reflected={}
                inspector=inspect(engines[0])
                for table in ['auth_sessions','feedback_v3','account_credentials']:
                    if table in inspector.get_table_names():reflected[table]={'columns':inspector.get_columns(table),'checks':inspector.get_check_constraints(table)}
                (out/'reflection.json').write_text(json.dumps(reflected,default=str,indent=2),encoding='utf-8')
            except Exception:pass
    finally:
        for engine in engines:engine.dispose()
        if server is not None and server.poll() is None:
            server.terminate()
            try:server.wait(timeout=30)
            except subprocess.TimeoutExpired:server.kill();server.wait(timeout=10)
        log.close()
        record={'version':version,'loopback_port':port,'checks':checks,'failures':failures,'server_stopped':server is not None and server.poll() is not None,'production_database_access':False,'provider_requests':0}
        (out/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        print(json.dumps(record))
    return bool(failures)


if __name__=='__main__':raise SystemExit(main())
