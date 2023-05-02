#!/bin/bash
if PGPASSWORD=odoo psql -h postgres-service  -p 5432  -U odoo  -d   postgres  -c '\l'  | grep -q 'odoo2'; then   echo "DB  exists"; \
else PGPASSWORD=odoo psql -h postgres-service  -p 5432  -U odoo  -d   postgres  -c 'CREATE DATABASE odoo2;'   \
&& PGPASSWORD=odoo psql  -h postgres-service  -p 5432 -U odoo  odoo2  < /mnt/db/DB/dump.sql >/db-creation.txt ; \
fi 
# if cat db-creation.txt | grep -q 'ALTER TABLE'; then  \
#  mkdir /mnt/data/filestore/odoo2   && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/odoo2/. ;  fi






#this script for install templat database###

# if cat db-creation.txt | grep -q 'ALTER TABLE'; then  \
#  mkdir /mnt/data/filestore/odoo2 >filestoredir.txt  && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/odoo2/. ;  fi




# #!/bin/bash

# if cat db-creation.txt | grep -q 'ALTER TABLE'; then mkdir /mnt/data/filestore/odoo2 ; \
# else cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/odoo2/.  fi

	
#     if mkdir /mnt/data/filestore/odoo2| grep -q 'ALTER TABLE'; then
#         STATEMENT2
# 	fi

# fi