#!/bin/bash
if PGPASSWORD=odoo psql -h postgres-service  -p 5432  -U odoo  -d   postgres  -c '\l'  | grep -q 'DB_NAME'; then   echo "DB  exists"; \
else PGPASSWORD=odoo psql -h postgres-service  -p 5432  -U odoo  -d   postgres  -c 'CREATE DATABASE DB_NAME;'   \
&& PGPASSWORD=odoo psql  -h postgres-service  -p 5432 -U odoo  DB_NAME  < /mnt/db/DB/dump.sql >/db-creation.txt ; \
fi 
