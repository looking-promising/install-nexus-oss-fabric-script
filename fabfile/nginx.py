import os

from fabric.api import *


@task
def install():
    path = os.path.abspath(__file__)
    dir_path = os.path.dirname(path)

    with settings(warn_only=True):
        sudo('service nginx stop')

    sudo('sudo apt-get install nginx')

    with cd(''):
        put(os.path.join(dir_path, 'nginx/nexus'), '/etc/nginx/sites-available/nexus', use_sudo=True)

    with cd('/etc/nginx/sites-enabled'):
        sudo('rm default')

        with settings(warn_only=True):
            sudo('rm default')

        sudo('ln -s ../sites-available/nexus nexus')

    sudo('service nginx start')
