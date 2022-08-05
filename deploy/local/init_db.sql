create database fdp;
CREATE USER django_fdp PASSWORD 'opensesame';
alter role django_fdp set client_encoding to 'utf8';
alter role django_fdp set default_transaction_isolation to 'read committed';
alter role django_fdp set timezone to 'UTC';
grant all privileges on database fdp to django_fdp;
ALTER USER django_fdp SUPERUSER;
