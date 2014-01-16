from fabric.api import *
from fabric.contrib.files import exists as fabric_exists
from fabric.contrib.files import sed as fabric_sed
from fabric.contrib.files import uncomment as fabric_uncomment
import os, defaults
import datetime


@task
def install():
    sudo('sudo apt-get install openjdk-7-jre-headless')
