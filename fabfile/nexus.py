__author__ = 'storjm'

from fabric.api import *
from fabric.contrib.files import exists as fabric_exists
import os, defaults
import datetime

env.user = 'ubuntu'


@task
def install(rsync_remote_install_path=None,
            nexus_username=defaults.nexus_user,
            download_url=defaults.download_url,
            install_dir=defaults.install_dir):
    print("TODO: install/upgrade nexus")

    # if nexus is already running, stop it
    stop_nexus()

    # create nexus user
    execute(create_user, username=nexus_username, home_dir=install_dir)

    # format a string from today's date
    today = datetime.datetime.now().strftime("%m-%d-%y")

    # setup the install options
    install_options = {
        'zip_file': today + "-" + os.path.basename(download_url),
        'download_url': download_url,
        'working_dir': "working",
        'nexus_current_dir_name': 'nexus-current',
        'nexus_old_dir_name': 'nexus-old-' + today,
        'rsync_remote_install_path': rsync_remote_install_path
    }

    # do the install work
    with cd(install_dir):
        # download the tar.gz file (-L follows redirects since the url may redirect to the actual file)
        sudo('curl -L -o %(zip_file)s %(download_url)s' % install_options)

        # create a working directory
        sudo('mkdir -p %(working_dir)s' % install_options)

        # extract the downloaded file
        sudo('tar xvzf %(zip_file)s -C %(working_dir)s' % install_options)

        # get the extracted directory name
        with cd(install_options['working_dir']):
            install_options['created_dir'] = os.path.join(install_options['working_dir'], sudo('ls | grep nexus'))

        # move the current nexus install into a backup dir
        if fabric_exists(install_options['nexus_current_dir_name']):
            sudo('mv %(nexus_current_dir_name)s %(nexus_old_dir_name)s' % install_options)

        # move the extracted directory from the working directory to the correct one
        sudo('mv %(created_dir)s %(nexus_current_dir_name)s' % install_options)

        # copy over the nexus conf dir
        if rsync_remote_install_path is not None:
            sudo('rsync -pr %(rsync_remote_install_path)s/conf %(nexus_current_dir_name)s/conf' % install_options)
            sudo('rsync -pr %(rsync_remote_install_path)s/../sonatype-work/nexus/conf %(nexus_current_dir_name)s/../sonatype-work' % install_options)

        elif fabric_exists(install_options['nexus_current_dir_name']):
            sudo('rsync -pr %(nexus_old_dir_name)s/conf %(nexus_current_dir_name)s/conf' % install_options)

        # recreate nexus symlink
        if fabric_exists('/usr/local/nexus'):
            sudo('rm /usr/local/nexus')

        with cd('/usr/local'):
            sudo('ln -s ' + install_dir + '/%(nexus_current_dir_name)s nexus' % install_options)

    # create starup script
    create_startup_script(install_dir, install_options['nexus_current_dir_name'])

    # make sure the nexus user owns everything in the install directory
    update_ownership(nexus_username, install_dir)

    # start the nexus service
    start_nexus()

    # cleanup working dir
    with settings(warn_only=True):
        sudo('rm -rf ' + install_dir + '/' + install_options['working_dir'])

    # install nginx
    install_nginx()

@task
def create_user(username=defaults.nexus_user, home_dir=defaults.install_dir):
    user_info = {
        "username": username,
        "home_dir": home_dir
    }
    #sudo useradd --home-dir /data/test/blah blah
    with settings(warn_only=True):
        sudo('id -u somename &>/dev/null || useradd --home-dir %(home_dir)s %(username)s' % user_info)

    sudo('mkdir -p ' + home_dir)
    update_ownership(username, home_dir)


def backup_conf_dir(install_dir=defaults.install_dir):
    # Important: Before upgrading, back up "sonatype-work/nexus/conf".  If you need to downgrade
    # for some reason, shut down the new server, restore the "conf" directory, and start up the old Nexus.

    backup_dir = 'sonatype-work/nexus/conf/ ' + 'conf-backup-' + datetime.datetime.now().strftime("%m-%d-%y-")

    with settings(warn_only=True):
        with cd(install_dir):
            sudo('cp -rf sonatype-work/nexus/conf/ ' + backup_dir)


@task
def create_startup_script(install_dir, nexus_current_dir_name):
    full_current_dir = os.path.join(install_dir, nexus_current_dir_name)
    #full_current_dir = install_dir + "/" + nexus_current_dir_name
    startup_script_path = os.path.join(full_current_dir, 'bin/nexus')

    if not fabric_exists('/etc/init.d/nexus'):
        with cd('/etc/init.d'):
            sudo('ln -s ' + startup_script_path + ' /etc/init.d/nexus')
            sudo('chmod 755 /etc/init.d/nexus')
            sudo('update-rc.d nexus defaults')

    """ TODO:

        Edit the init script changing the following variables:

        Change NEXUS_HOME to the absolute folder location e.g. NEXUS_HOME="/usr/local/nexus"
        Set the RUN_AS_USER to nexus or any other user with restricted rights that you want to use to run the service. You should not be running Nexus as root.
        Change PIDDIR to a directory where this user has read/write permissions. In most Linux distributions, /var/run is only writable by root. The properties you need to add to customize the PID file location is "wrapper.pid". For more information about this property and how it would be configured in wrapper.conf, see: http://wrapper.tanukisoftware.com/doc/english/properties.html

    """


def stop_nexus():
    with settings(warn_only=True):
        sudo('service nexus stop')


def start_nexus():
    sudo('service nexus start')


def update_ownership(nexus_user, directory):
    user_info = {
        "username": nexus_user,
        "home_dir": directory
    }
    sudo('chown -R %(username)s:%(username)s %(home_dir)s' % user_info)


def install_nginx():
    print('TODO: install nginx')
