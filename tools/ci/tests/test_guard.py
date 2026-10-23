"""Only execute through run.py --suite guard (never ordinary unguarded pytest)."""
import asyncio
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

main = sys.modules.get('__main__')
guard_class = getattr(main, 'OfflineGuard', None)
if guard_class is None or not isinstance(getattr(main, 'ACTIVE_GUARD', None), guard_class):
    raise RuntimeError('Execute these probes only through the guarded runner')

import pytest


def test_standard_library_socketpair():
    left, right = socket.socketpair()
    try:
        left.sendall(b'left')
        assert right.recv(4) == b'left'
        right.sendall(b'right')
        assert left.recv(5) == b'right'
    finally:
        left.close()
        right.close()


def test_asyncio_self_pipe():
    async def task():
        await asyncio.sleep(0)
        return 42
    assert asyncio.run(task()) == 42


def test_external_tcp_blocked():
    with socket.socket() as sock, pytest.raises(RuntimeError, match='CI offline guard blocked'):
        sock.connect(('192.0.2.1', 443))


def test_local_service_blocked():
    with socket.socket() as sock, pytest.raises(RuntimeError, match='CI offline guard blocked'):
        sock.connect(('127.0.0.1', 8765))


def test_dns_blocked():
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        socket.getaddrinfo('provider.invalid', 443)


def test_host_name_lookup_blocked():
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        socket.gethostbyname('provider.invalid')


def test_reverse_lookup_blocked():
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        socket.gethostbyaddr('192.0.2.1')


def test_getnameinfo_blocked():
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        socket.getnameinfo(('192.0.2.1', 443), 0)


def test_bind_blocked():
    with socket.socket() as sock, pytest.raises(RuntimeError, match='CI offline guard blocked'):
        sock.bind(('127.0.0.1', 0))


def test_datagram_blocked():
    with socket.socket(type=socket.SOCK_DGRAM) as sock, pytest.raises(RuntimeError, match='CI offline guard blocked'):
        sock.sendto(b'not sent', ('192.0.2.1', 8765))


def test_subprocess_blocked():
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        subprocess.run([sys.executable, '-c', 'raise SystemExit(123)'], check=False)


def test_shell_blocked():
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        os.system('exit 123')


def test_database_outside_sandbox_blocked():
    outside = Path(os.environ['CI_DB_SANDBOX']).parent/'not-created.sqlite'
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        sqlite3.connect(outside)
    assert not outside.exists()


def test_database_uri_blocked():
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        sqlite3.connect('file:unapproved.sqlite?mode=memory&cache=shared', uri=True)


def test_database_empty_blocked():
    with pytest.raises(RuntimeError, match='CI offline guard blocked'):
        sqlite3.connect('')


def test_database_attach_empty_blocked():
    db = sqlite3.connect(':memory:')
    try:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("ATTACH DATABASE '' AS external")
    finally:
        db.close()


def test_database_inside_sandbox():
    with sqlite3.connect(Path(os.environ['CI_DB_SANDBOX'])/'allowed.sqlite') as connection:
        assert connection.execute('SELECT 1').fetchone() == (1,)


def test_memory_database():
    with sqlite3.connect(':memory:') as connection:
        assert connection.execute('SELECT 1').fetchone() == (1,)


def test_database_attach_outside_blocked():
    target = Path(os.environ['CI_DB_SANDBOX']).parent/'not-attached.sqlite'
    db = sqlite3.connect(':memory:')
    try:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute('ATTACH DATABASE ? AS external', (str(target),))
        assert not target.exists()
    finally:
        db.close()


def test_database_vacuum_outside_blocked():
    target = Path(os.environ['CI_DB_SANDBOX']).parent/'not-vacuumed.sqlite'
    db = sqlite3.connect(':memory:')
    try:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute('VACUUM INTO ?', (str(target),))
        assert not target.exists()
    finally:
        db.close()


def test_database_attach_inside_sandbox():
    target = Path(os.environ['CI_DB_SANDBOX'])/'attached.sqlite'
    db = sqlite3.connect(':memory:')
    try:
        # Authorizer runs before parameter binding; a parameterized target is
        # deliberately unverifiable/fail-closed. This known literal is escaped.
        db.execute("ATTACH DATABASE '" + str(target).replace("'", "''") + "' AS controlled")
        db.execute('CREATE TABLE controlled.proof(value INTEGER)')
        db.execute('INSERT INTO controlled.proof VALUES(42)')
        assert db.execute('SELECT value FROM controlled.proof').fetchone() == (42,)
    finally:
        db.close()


def test_enable_extension_blocked():
    db = sqlite3.connect(':memory:')
    try:
        with pytest.raises(RuntimeError, match='CI offline guard blocked'):
            db.enable_load_extension(True)
    finally:
        db.close()


def test_load_extension_blocked():
    db = sqlite3.connect(':memory:')
    try:
        with pytest.raises(RuntimeError, match='CI offline guard blocked'):
            db.load_extension('synthetic-unavailable')
    finally:
        db.close()


def test_sql_load_extension_blocked():
    db = sqlite3.connect(':memory:')
    try:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("SELECT load_extension('synthetic-unavailable')")
    finally:
        db.close()
