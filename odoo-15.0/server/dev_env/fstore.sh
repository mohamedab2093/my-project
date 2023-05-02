#!/bin/bash
# if cat /db-creation.txt | grep -q 'ALTER TABLE'; then  \
#    mkdir /mnt/data/filestore/DB_NAME   && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/DB_NAME/. ;  fi
# if cat /db-creation.txt | grep -q 'ALTER TABLE'; && [ ! -d /mnt/data/filestore/DB_NAME ] then  \
#    mkdir /mnt/data/filestore/DB_NAME   && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/DB_NAME/. ;  fi



if [ ! -d /mnt/data/filestore/DB_NAME  ]; then \
  mkdir -p /mnt/data/filestore/DB_NAME && cp   -R /mnt/db/DB/filestore/*  /mnt/data/filestore/DB_NAME/. ;
fi






