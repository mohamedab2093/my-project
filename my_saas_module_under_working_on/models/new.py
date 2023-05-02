import subprocess
def create_nodejs_dockerfile():
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
                #COPY addons_ci /mnt/addons_ci
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
    image_name = 'my-nodejs-app'
    cmd = ['docker', 'build', '-t', image_name, '.']
    result = subprocess.run(cmd, cwd='/home/odoo15i/odoo-dockerfile/server/', capture_output=True)
    image_id = result.stdout.decode().strip()
    # Create a Docker container
    container_name = 'my-nodejs-container'
    cmd = ['docker', 'run', '-d', '--name', container_name, image_name]
    result = subprocess.run(cmd, capture_output=True)
    container_id = result.stdout.decode().strip()
    print("success")
    print(image_name)
    print(container_name)
create_nodejs_dockerfile()



# my_module/models/my_model.py

