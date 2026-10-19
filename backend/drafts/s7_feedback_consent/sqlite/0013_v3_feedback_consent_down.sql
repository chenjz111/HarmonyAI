-- NOT A STANDALONE EXECUTABLE DOWN. No destructive DDL is present here.
-- Use migration.remove_sqlite(): BEGIN IMMEDIATE, verified history/checksum,
-- exact installed schema/objects, no extension data and no external dependencies.
-- It drops owned triggers/index, then learning_consent before referenced columns,
-- drops nullable extension columns and the isolated review ledger atomically.
SELECT int2_0013_requires_verified_downgrade_executor();
