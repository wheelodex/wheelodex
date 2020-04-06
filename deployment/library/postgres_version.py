#!/usr/bin/python3
from   distutils.version import LooseVersion
import os
import traceback

# Note: "SELECT version();" returns a string that is entirely useless for our
# purposes, so we have to look inside directories instead.

pgdir = '/usr/lib/postgresql'  # where the init.d script looks for versions

def main():
    module = AnsibleModule(argument_spec={}, supports_check_mode=True)
    try:
        versions = os.listdir(pgdir)
    except EnvironmentError as e:
        module.fail_json(msg='Could not read %s directory: %s' % (pgdir, e))
    if not versions:
        module.fail_json(msg='No PostgreSQL versions found')
    try:
        latest = max(versions, key=LooseVersion)
    except Exception:
        module.fail_json(msg=traceback.format_exc())
    module.exit_json(changed=False, ansible_facts={"postgres_version": latest})

from ansible.module_utils.basic import *
main()
