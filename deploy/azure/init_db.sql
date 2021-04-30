create database fdp;
alter role fdpdjango set client_encoding to 'utf8';
alter role fdpdjango set default_transaction_isolation to 'read committed';
alter role fdpdjango set timezone to 'UTC';
grant all privileges on database fdp to fdpdjango;
