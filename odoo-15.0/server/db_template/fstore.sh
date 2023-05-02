#!/bin/bash
# if cat /db-creation.txt | grep -q 'ALTER TABLE'; then  \
#    mkdir /mnt/data/filestore/odoo2   && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/odoo2/. ;  fi
# if cat /db-creation.txt | grep -q 'ALTER TABLE'; && [ ! -d /mnt/data/filestore/odoo2 ] then  \
#    mkdir /mnt/data/filestore/odoo2   && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/odoo2/. ;  fi



if [ ! -d /mnt/data/filestore/odoo2  ]; then \
  mkdir -p /mnt/data/filestore/odoo2 && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/odoo2/. ;
fi






