# my_module/models/my_model.py

from odoo import models, fields, api
import subprocess

class MyModel(models.Model):
    _name = 'my.saas'

    name = fields.Char(string="customer name")
    image_name = fields.Char(string="image name ",readonly=True)
    container_name=fields.Char(string="Container name",readonly=True)
    odoo_version = [
        ('odoo15', 'Odoo15'),
        ('odoo14', 'Odoo14'),
    ]
    container_test = fields.Char(string="Container test",readonly=False)

    @api.model
    def create(self, vals):
        # Create the record
        record = super(MyModel, self).create(vals)

        # Create the Docker container
        record.create_nodejs_dockerfile()

        return record
    @api.model
    def create_nodejs_dockerfile(self):
        # Define the Dockerfile contents
        dockerfile_contents = """
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
                    COPY image-configs/dev.conf /etc/odoo/odoo.conf
                    COPY custom_addons /mnt/custom_addons
                    #COPY ./addons_extra /mnt/addons_extra
                    EXPOSE 8069 8071 8072
                    #USER odoo
                    ENTRYPOINT ["/entrypoint.sh"]
                    CMD ["odoo"]

        """

        # Save the Dockerfile to a file
        dockerfile_path = '/home/odoo15i/odoo-dockerfile/server/Dockerfile'
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_contents)

        # Build the Docker image
        image_name = ("image"+self.name)
        cmd = ['docker', 'build', '-t', image_name, '.']
        result = subprocess.run(cmd, cwd='/home/odoo15i/odoo-dockerfile/server/', capture_output=True)
        image_id = result.stdout.decode().strip()  # Get the image ID from the output
        # Create a Docker container
        container_name = ("container"+self.name)
        cmd = ['docker', 'run', '-d', '--name', container_name, image_name]
        result = subprocess.run(cmd, capture_output=True)
        container_id = result.stdout.decode().strip()  # Get the container ID from the output
        self.write({
            'image_name': image_name,
            'container_name': container_name,
        })
        print("success")
        # print(container_id)
        # print(image_id)


        # print(self.container_test)


        # Return a success message
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Node.js Docker Container',
        #     'view_mode': 'form',
        #     'res_model': 'my_saas',
        #     'target': 'current',
        #     'res_id': self.id,
        #     'context': {'message': 'Node.js Docker container created successfully.'},
        # }
#============================