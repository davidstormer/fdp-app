create database fdp;
alter role fdp set client_encoding to 'utf8';
alter role fdp set default_transaction_isolation to 'read committed';
alter role fdp set timezone to 'UTC';
grant all privileges on database fdp to fdp;
