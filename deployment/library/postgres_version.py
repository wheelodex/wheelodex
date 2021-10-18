#!/usr/bin/python3
import os
import traceback
from   packaging.version import Version

# Note: "SELECT version();" returns a string that is entirely useless for our
# purposes, so we have to look inside directories instead.

pgdir = '/usr/lib/postgresql'  # where the init.d script looks for versions

def main():
    module = AnsibleModule(argument_spec={}, supports_check_mode=True)
    try:
        versions = os.listdir(pgdir)
    except IOError as e:
        module.fail_json(msg=f'Could not read {pgdir} directory: {e}')
    if not versions:
        module.fail_json(msg='No PostgreSQL versions found')
    try:
        latest = max(versions, key=Version)
    except Exception:
        module.fail_json(msg=traceback.format_exc())
    module.exit_json(changed=False, ansible_facts={"postgres_version": latest})

from ansible.module_utils.basic import *
main()
