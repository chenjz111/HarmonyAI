"""Driver-boundary tests; no MySQL connection or provider access."""
from contextlib import contextmanager

import pytest

from backend.app.core import v3_migrations as migrations


class RecordingEngine:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    @contextmanager
    def begin(self):
        yield self

    def exec_driver_sql(self, sql, parameters=None, execution_options=None):
        if sql.startswith(('CREATE TRIGGER', 'CREATE TABLE after_trigger')):
            assert execution_options == {'no_parameters': True}
        self.calls.append((sql, parameters))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError('synthetic DDL failure')
        return self

    def first(self):
        return None


def apply(sql, *, fail_on=None):
    engine = RecordingEngine(fail_on)
    migrations._apply_mysql_migration(
        engine, 'test_driver_boundary', sql, 'synthetic-checksum',
        session_upgrade=False,
    )
    return engine


def test_compound_trigger_reaches_driver_whole_and_ledger_is_last():
    trigger = ("CREATE TRIGGER guard_feedback BEFORE UPDATE ON feedback_v3 FOR EACH ROW\n"
               "BEGIN\n IF NEW.id <> OLD.id THEN\n"
               " SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='immutable; value';\n"
               " END IF;\nEND")
    engine = apply(trigger + '; CREATE TABLE after_trigger(id INT);')
    assert engine.calls[2][0] == trigger
    assert engine.calls[3][0] == 'CREATE TABLE after_trigger(id INT)'
    assert engine.calls[4][0].startswith('INSERT INTO schema_migrations')
    assert len(engine.calls) == 5


def test_simple_trigger_and_quoted_semicolons_are_single_statements():
    engine = apply("CREATE TRIGGER no_delete BEFORE DELETE ON feedback_v3 FOR EACH ROW "
                   "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='can''t; delete';"
                   "INSERT INTO `semi;colon` VALUES ('x; -- y', \"z;#w\");")
    assert engine.calls[2][0].endswith("MESSAGE_TEXT='can''t; delete'")
    assert engine.calls[3][0] == 'INSERT INTO `semi;colon` VALUES (\'x; -- y\', "z;#w")'
    assert len(engine.calls) == 5


def test_comments_do_not_create_phantom_statements_or_block_tokens():
    engine = apply("-- BEGIN; END;\n# another; comment\n"
                   "CREATE TABLE a(id INT /* ; BEGIN END */); -- trailing;\n")
    assert len(engine.calls) == 4
    assert 'CREATE TABLE a' in engine.calls[2][0]


@pytest.mark.parametrize('sql', [
    "CREATE TABLE a(id INT); SELECT 'unfinished;",
    'CREATE TABLE a(id INT); /* unfinished',
    'CREATE TRIGGER t BEFORE DELETE ON a FOR EACH ROW BEGIN SELECT 1;',
    'DELIMITER $$\nCREATE TABLE a(id INT)$$',
    '/*!50003 CREATE TRIGGER t BEFORE DELETE ON a FOR EACH ROW SET @x=1 */;',
    'CREATE TABLE a(id INT); CREATE DEFINER=`u`@`h` TRIGGER t BEFORE DELETE ON a FOR EACH ROW BEGIN SELECT 1; SELECT 2; END;',
    "CREATE TABLE a(id INT); SELECT 'ambiguous\\'; SELECT 1; -- ';",
])
def test_unverifiable_script_rejected_before_migration_ddl_or_ledger(sql):
    engine = RecordingEngine()
    with pytest.raises(ValueError):
        migrations._apply_mysql_migration(engine, 'test_driver_boundary', sql,
                                         'synthetic-checksum', session_upgrade=False)
    assert len(engine.calls) == 2  # ledger creation/read only, no migration DDL


def test_driver_failure_never_records_successful_migration():
    engine = RecordingEngine(fail_on='CREATE TRIGGER')
    with pytest.raises(RuntimeError, match='synthetic DDL failure'):
        migrations._apply_mysql_migration(
            engine, 'test_driver_boundary',
            'CREATE TABLE a(id INT); CREATE TRIGGER t BEFORE DELETE ON a FOR EACH ROW '
            "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='blocked';",
            'synthetic-checksum', session_upgrade=False,
        )
    assert not any(sql.startswith('INSERT INTO schema_migrations') for sql, _ in engine.calls)
