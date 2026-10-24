-- Fail closed: do not discard credentials, revocations or replay evidence.
SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='0014 account evidence downgrade requires reviewed operator recovery';
