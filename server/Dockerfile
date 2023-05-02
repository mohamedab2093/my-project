FROM odoo:12.0
LABEL maintainer="Oakland  Tech <m.abdalla@odooerp.ae>"

USER root

#COPY addons_dependencies /mnt/addons_dependencies
COPY image-scripts/entrypoint.sh /

RUN chmod +x /entrypoint.sh

RUN mkdir -p /mount/data

RUN touch  /mount/data/odoo.log

RUN chmod  777  /mount/data

RUN chmod 777  /mount/data/odoo.log

#RUN apt-get update -y && apt-get install -y apt-utils && apt-get  install vim -y && apt-get install htop -y && apt-get install nano -y && apt install iputils-ping -y
#apt-utils

RUN pip3 install crypto

#COPY addons_ci /mnt/addons_ci
COPY image-configs/dev.conf /etc/odoo/odoo.conf

COPY custom_addons /mnt/custom_addons

#COPY ./addons_extra /mnt/addons_extra
EXPOSE 8069 8071 8072

#USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
