from fabric.api import *
from fabric.contrib.files import exists as fabric_exists
from fabric.contrib.files import sed as fabric_sed
from fabric.contrib.files import uncomment as fabric_uncomment
import os, datetime

import defaults, open_jdk, nginx

__all__ = ['install', 'create_user', 'setup_startup_script', 'start_nexus', 'stop_nexus', 'backup_existing_install']

env.user = 'ubuntu'


@task
def install(nexus_username=defaults.nexus_user,
             download_url=defaults.download_url,
             install_dir=defaults.install_dir,
             migrate_from=None,
             install_jdk=True,
             install_nginx=True):

    # need java to run nexus
    open_jdk.install()

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
        'migrate_from': migrate_from,
        'sym_linked_nexus_dir': '/usr/local/nexus'
    }

    # get the pakage to install
    install_options['created_dir'] = download_and_extract(install_dir, install_options)

    # backup any existing install files
    backup_existing_install(install_dir, install_options)

    # setup/install the downloaded version
    setup_downloaded_version(install_dir, install_options)

    # migrate previous install config / packages
    migrate_previous_install(install_dir, install_options, migrate_from)

    # make sure the startup script is in place
    setup_startup_script(install_dir,
                         install_options['nexus_current_dir_name'],
                         install_options['sym_linked_nexus_dir'],
                         nexus_username)

    # make sure the nexus user owns everything in the install directory
    update_ownership(nexus_username, install_dir)

    # start the nexus service
    start_nexus()

    # cleanup working dir
    with settings(warn_only=True):
        sudo('rm -rf ' + install_dir + '/' + install_options['working_dir'])

    nginx.install()


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


@task
def backup_existing_install(install_dir, install_options):

    with cd(install_dir):
        # move the current nexus install into a backup dir
        if fabric_exists(install_options['nexus_current_dir_name']):
            sudo('mv %(nexus_current_dir_name)s %(nexus_old_dir_name)s' % install_options)

@task
def setup_startup_script(install_dir, nexus_current_dir_name, sym_linked_nexus_dir, nexus_username):
    full_current_dir = os.path.join(install_dir, nexus_current_dir_name)
    startup_script_path = os.path.join(full_current_dir, 'bin/nexus')

    if not fabric_exists('/etc/init.d/nexus'):
        with cd('/etc/init.d'):
            sudo('ln -s ' + startup_script_path + ' /etc/init.d/nexus')
            sudo('chmod 755 /etc/init.d/nexus')
            sudo('update-rc.d nexus defaults')

    # Edit the init script changing the following variables:
    #    * Change NEXUS_HOME to the absolute folder location e.g. NEXUS_HOME="/usr/local/nexus"
    #    * Set the RUN_AS_USER to nexus or any other user with restricted rights that you want to use to run the service
    #
    # update nexus home first
    before = 'NEXUS_HOME=\".+\"'
    after = 'NEXUS_HOME=\"' + sym_linked_nexus_dir + '\"'
    fabric_sed(startup_script_path, before, after, use_sudo=True, backup='.bak')

    # make sure the RUN_AS_USER variable is not commented out
    fabric_uncomment(startup_script_path, 'RUN_AS_USER=', use_sudo=True, char='#', backup='.bak')

    # now update RUN_AS_USER
    before = '^\s*RUN_AS_USER=.*'
    after = 'RUN_AS_USER=\"' + nexus_username + '\"'
    fabric_sed(startup_script_path, before, after, use_sudo=True, backup='.bak')


@task
def stop_nexus():
    with settings(warn_only=True):
        sudo('service nexus stop')


@task
def start_nexus():
    sudo('service nexus start')


def update_ownership(nexus_user, directory):
    user_info = {
        "username": nexus_user,
        "home_dir": directory
    }
    sudo('chown -R %(username)s:%(username)s %(home_dir)s' % user_info)


def download_and_extract(install_dir, install_options):

    with cd(install_dir):
        # download the tar.gz file (-L follows redirects since the url may redirect to the actual file)
        sudo('curl -L -o %(zip_file)s %(download_url)s' % install_options)

        # create a working directory
        sudo('mkdir -p %(working_dir)s' % install_options)

        # extract the downloaded file
        sudo('tar xvzf %(zip_file)s -C %(working_dir)s' % install_options)

        # get the extracted directory name
        with cd(install_options['working_dir']):
            return os.path.join(install_options['working_dir'], sudo('ls | grep nexus'))


def setup_downloaded_version(install_dir, install_options):

    with cd(install_dir):
        # move the extracted directory from the working directory to the correct one
        sudo('mv %(created_dir)s %(nexus_current_dir_name)s' % install_options)

        symlink = install_options['sym_linked_nexus_dir']

        # delete the symlink if it exists
        if fabric_exists(symlink):
            sudo('rm ' + symlink)

        # recreate nexus symlink
        parent_dir = os.path.dirname(symlink)
        print(parent_dir)
        with cd(parent_dir):
            sudo('ln -s ' + install_dir + '/%(nexus_current_dir_name)s nexus' % install_options)


def migrate_previous_install(install_dir, install_options, migrate_from):

    with cd(install_dir):
        # copy over the nexus conf dir
        if migrate_from is not None:
            sudo('mkdir -p %(nexus_current_dir_name)s/../sonatype-work' % install_options)
            sudo('rsync -pr %(migrate_from)s/conf %(nexus_current_dir_name)s/conf && rsync -pr %(migrate_from)s/../sonatype-work %(nexus_current_dir_name)s/../sonatype-work' % install_options)

        elif fabric_exists(install_options['nexus_current_dir_name']):
            sudo('rsync -pr %(nexus_old_dir_name)s/conf %(nexus_current_dir_name)s/conf' % install_options)
