#!/bin/bash
if PGPASSWORD=odoo psql -h postgres-service  -p 5432  -U odoo  -d   postgres  -c '\l'  | grep -q 'DB_NAME'; then   echo "DB  exists"; \
else PGPASSWORD=odoo psql -h postgres-service  -p 5432  -U odoo  -d   postgres  -c 'CREATE DATABASE DB_NAME;'   \
&& PGPASSWORD=odoo psql  -h postgres-service  -p 5432 -U odoo  DB_NAME  < /mnt/db/DB/dump.sql >/db-creation.txt ; \
fi 
# if cat db-creation.txt | grep -q 'ALTER TABLE'; then  \
#  mkdir /mnt/data/filestore/DB_NAME   && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/DB_NAME/. ;  fi






#this script for install templat database###

# if cat db-creation.txt | grep -q 'ALTER TABLE'; then  \
#  mkdir /mnt/data/filestore/DB_NAME >filestoredir.txt  && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/DB_NAME/. ;  fi




# #!/bin/bash

# if cat db-creation.txt | grep -q 'ALTER TABLE'; then mkdir /mnt/data/filestore/DB_NAME ; \
# else cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/DB_NAME/.  fi

	
#     if mkdir /mnt/data/filestore/DB_NAME| grep -q 'ALTER TABLE'; then
#         STATEMENT2
# 	fi

# fi