-- Run locally as a MySQL administrator. Replace the placeholder passwords.
-- The URL in .env connects over TCP to 127.0.0.1, so these accounts use that host.
-- MySQL 8.0.16+ is required by the project's enforced CHECK constraints.

CREATE DATABASE IF NOT EXISTS smart_meter_explorer
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'sme_app'@'127.0.0.1'
  IDENTIFIED BY 'REPLACE_WITH_A_LONG_UNIQUE_RUNTIME_PASSWORD';

CREATE USER IF NOT EXISTS 'sme_migrator'@'127.0.0.1'
  IDENTIFIED BY 'REPLACE_WITH_A_DIFFERENT_LONG_UNIQUE_MIGRATION_PASSWORD';

GRANT SELECT, INSERT, UPDATE, DELETE
  ON smart_meter_explorer.* TO 'sme_app'@'127.0.0.1';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, INDEX, REFERENCES
  ON smart_meter_explorer.* TO 'sme_migrator'@'127.0.0.1';

FLUSH PRIVILEGES;

-- Confirm the grants before using the app:
SHOW GRANTS FOR 'sme_app'@'127.0.0.1';
SHOW GRANTS FOR 'sme_migrator'@'127.0.0.1';
