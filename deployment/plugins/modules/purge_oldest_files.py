#!/usr/bin/python3
import os
import os.path
import traceback

def main():
    module = AnsibleModule(
        argument_spec={
            "path": {"required": True, "type": "path"},
            "keep": {"required": True, "type": "int"},
        },
        supports_check_mode=True,
    )
    path = module.params["path"]
    keep = module.params["keep"]
    changed = False
    try:
        files = os.listdir(path)
        if len(files) > keep:
            changed = True
            if not module.check_mode:
                files.sort(key=lambda f: os.stat(os.path.join(path,f)).st_mtime)
                for f in files[:-keep]:
                    os.unlink(os.path.join(path, f))
    except Exception:
        module.fail_json(msg=traceback.format_exc())
    module.exit_json(changed=changed)

from ansible.module_utils.basic import *
main()
