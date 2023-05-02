FROM odoo:15.0
LABEL maintainer="Oakland  Tech <m.abdalla@odooerp.ae>"
#ARG ACCESS_TOKEN
#ENV ACCESS_TOKEN=$ACCESS_TOKEN


USER root

COPY addons_dependencies /mnt/addons_dependencies
COPY image-scripts/entrypoint.sh /
RUN chmod +x /entrypoint.sh


RUN mkdir -p /mount/data
RUN mkdir -p /mnt/db



#RUN chown  odoo:odoo -R /mount/data
RUN chmod  777  /mount/data
RUN apt-get update -y && apt-get  install vim -y && apt-get install htop -y && apt-get install nano -y










# RUN pip3 install redis

#COPY addons_ci /mnt/addons_ci
COPY image-configs/dev.conf /etc/odoo/odoo.conf
#RUN chmod 777 /etc/odoo/odoo.conf
#RUN chown odoo:odoo -R /etc/odoo/


COPY custom_addons /mnt/custom_addons
COPY db_template /mnt/db
RUN chmod  777  /mnt/db
RUN chmod  777  /mnt/db/psql.sh
RUN chmod  777  /mnt/db/fstore.sh


# RUN apt-get update -y  && apt-get install vim -y && apt-get install htop -y && apt-get install unzip -y && bash /mnt/db/psql.sh
# && PGPASSWORD=odoo psql -h postgres-service  -p 5432  -U odoo  -d   postgres  -c "CREATE DATABASE newodoo" ;  && PGPASSWORD=odoo psql  -h postgres-service  -p 5432 -U odoo  newodoo  < /mnt/db/DB/dump.sql
#COPY db_template/DB/filestore/*  /mnt/data/filestore/odoo/.

#COPY ./addons_extra /mnt/addons_extra
EXPOSE 8069 8071 8072

#USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
