"""
                    FROM odoo:12.0
                    LABEL maintainer="ROOTS  Tech <m.abdalla@roots.io>"
                    USER root
                    #COPY addons_dependencies /mnt/addons_dependencies
                    COPY entrypoint.sh /
                    RUN chmod +x /entrypoint.sh
                    RUN mkdir -p /mount/data
                    RUN touch  /mount/data/odoo.log
                    RUN chmod  777  /mount/data
                    RUN chmod 777  /mount/data/odoo.log
                    RUN apt-get update -y && apt-get install -y apt-utils && apt-get  install vim -y && apt-get install htop -y && apt-get install nano -y && apt install iputils-ping -y
                    RUN pip3 install crypto
                    #RUN pip install pycrypto
                    #COPY addons_ci /mnt/addons_ci
                    COPY image-configs/dev.conf /etc/odoo/odoo.conf
                    COPY custom_addons /mnt/custom_addons
                    #COPY ./addons_extra /mnt/addons_extra
                    EXPOSE 8069 8071 8072
                    #USER odoo
                    ENTRYPOINT ["/entrypoint.sh"]
                    CMD ["odoo"]

        """