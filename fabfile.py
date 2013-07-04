# -*- coding: utf-8 -*-
"""Fabric tasks and automation for DM Ex Machina builds.


This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <http://unlicense.org/>

"""
##
from fabric import api, colors, state, utils
from fabric.api import env

##
# Most Fabric output just fucks up my chi.
for op in ('running', 'stdout', 'stderr', 'status'):
    state.output[op] = False


##
class VM(object):
    """Creates a transient virtual machine for development.

    This VM can be torn down when control leaves this context manager,
    which is the default behaviour, or be left around for further
    testing and hacking.

    """

    def __init__(self, teardown=True):
        """Automatically provision the virtual machine.

        The `teardown` parameter indicates whether or not to destroy the
        machine when control leaves this context manager.

        """
        self.teardown = teardown

        utils.fastprint("Setting up a virtual machine ... ")
        with api.settings(warn_only=True):
            setup = api.local('vagrant up', True)
            if setup.failed:
                print(colors.magenta("fail", True))
                print("Logs:")
                print(setup)
            else:
                print(colors.green(" ok ", True))

    def __enter__(self):
        """Extract SSH info for this VM."""
        utils.fastprint("Retrieving SSH info for the VM ... ")
        VM.get_ssh_info()
        print(colors.green(" ok ", True))

    def __exit__(self, *args, **kwargs):
        """Destroy the VM automatically when it is not needed."""
        utils.fastprint("Clearing SSH info from the VM ... ")
        VM.clear_ssh_info()
        print(colors.green(" ok ", True))

        if self.teardown:
            utils.fastprint("Tearing down the virtual machine ... ")
            api.local('vagrant destroy', True)
            print(colors.green(" ok ", True))
        else:
            print(colors.yellow("Not tearing down virtual machine ... ", True))

    @staticmethod
    def get_ssh_info():
        """Retrieves and sets SSH information for the VM.

        This allows tests and other commands to automatically run on the
        VM without needing to worry about specifying host information
        manually.

        """
        VM.old_env_keyfilename = env.key_filename
        VM.old_env_hoststring = env.host_string

        ssh_info = api.local('vagrant ssh-config', True).splitlines()[1:]
        ssh_info = dict([
            l.strip().split(' ', 1) for l in ssh_info if l.strip()])

        env.key_filename = ssh_info['IdentityFile']
        env.host_string = 'vagrant@%(HostName)s:%(Port)s' % ssh_info

    @staticmethod
    def clear_ssh_info():
        """Resets SSH info to what it was before the VM was called."""
        env.key_filename = VM.old_env_keyfilename
        env.host_string = VM.old_env_hoststring


##
@api.task
def real():
    """Setup the environment for the real server."""
    env.host_string = 'ubuntu@dmexmachina.com'


@api.task(alias='style-check')
def style_check():
    """Runs Python static code checkers against the code.

    Although more for style reasons, these are quite helpful in
    identifying problems with the code. A file will be generated at
    ./.logs/style.log for perusal.

    Due to how pylint works it must be invoked manually.

    """
    utils.fastprint("Checking Python code style ... ")
    with api.settings(api.hide('warnings'), warn_only=True):
        pep8 = api.local('pep8 .', True)
        pyflakes = api.local('pyflakes .', True)

        # Print them out to a file so we can peruse them later.
        log = open('./.log/style.log', 'w')
        log.write("pep8:\n%s\n\npyflakes:\n%s" % (pep8, pyflakes))

    if pep8:
        print(colors.magenta("fail", True))
    elif pyflakes:
        print(colors.magenta("fail", True))
    else:
        print(colors.green(" ok ", True))

    if pep8 or pyflakes:
        print(colors.magenta("Please check ./.log/style.log.", True))

    print(colors.yellow("Please be sure to run pylint manually.", True))

    return (pep8 and pyflakes)


@api.task
def bootstrap():
    """Installs Puppet in a blank environment for config updates."""
    utils.fastprint("Installing base environment ... ")
    api.sudo('apt-get update')  # Required so we don't have random 404s.
    api.sudo('apt-get install -y puppet')
    print(colors.green(" ok ", True))


@api.task
def provision():
    """Executes the most recent Puppet config on the server.

    This saves a lot of trouble of getting SSL and puppetmasterd setup.

    """
    utils.fastprint("Updating server configuration ... ")
    api.put('./config/*', '/tmp', use_sudo=True)
    with api.settings(api.hide('warnings'), warn_only=True):
        puppet = api.sudo('''
            puppet apply --modulepath=/tmp/modules /tmp/site.pp''')
    print(colors.green(" ok ", True))
    print(puppet)


@api.task(alias='test')
def run_tests():
    """Runs unit tests upon deployment or when testing in Vagrant.

    These tests are designed to be atomic enough to run in production
    environments as well.

    """
    utils.fastprint("Running all defined tests ... ")
    with api.settings(api.hide('warnings'), warn_only=True):
        with api.cd('/project'):
            nose = api.sudo('''
                nosetests ./tests/*.py -v --with-coverage \
                --cover-package=dmxm
            ''', True)

            # We don't really care about the generated coverage file.
            api.sudo('rm -rf ./.coverage')

    if nose.failed:
        print(colors.magenta("fail", True))
        print(colors.magenta(nose, True))
    else:
        print(colors.green(" ok ", True))
        print(colors.cyan(nose, True))


@api.task(alias='test-build')
def full_test_build():
    """Builds and runs the full suite of tests on this code.

    This includes building the VM, running Puppet, setting up the code,
    running all unit and functional tests, and verifying that everything
    works exactly as intended.

    Long process is long, so use this full build sparingly.

    """
    style_check()
    with VM():
        bootstrap()
        provision()
        run_tests()


@api.task()
def workon():
    """Creates a virtual environment but does not tear it down.

    You can continue to edit ./src and run tests without needing to
    rebuild and spend 10 minutes waiting for each build to work (which
    is quite maddening when looking for bugs).

    Make sure changes that you make are reflected in Puppet manifests
    so they are applied to future `workon` or `full_test_build` calls.

    """
    with VM(teardown=False):
        bootstrap()
        provision()


@api.task(alias='vm')
def dev_vm():
    """Retrieves and sets SSH information for the VM.

    This allows tests and other commands to be remotely run without
    needing to specify host information on the command line.

    Sample invocation: `fab vm test`.

    """
    VM.get_ssh_info()


@api.task
def upload():
    """Copies code over to the server.

    Really only ever used on production deployments as the development
    versions have the folders synced up.

    """
    utils.fastprint("Copying new code to the server ... ")
    api.put('./src/*', '/projects/dmxm/', use_sudo=True)

    # Chown the files so that they work properly in Apache2.
    api.sudo('chown -R dmxm:dmxm /projects/dmxm/*')
    print(colors.green(" ok ", True))


@api.task
def kick():
    """Give Apache and MongoDB a restart."""
    utils.fastprint("Restarting MongoDB ... ")
    api.sudo('service mongodb restart')
    print(colors.green(" ok ", True))

    utils.fastprint("Restarting Apache2 ... ")
    api.sudo('service apache2 restart')
    print(colors.green(" ok " , True))
