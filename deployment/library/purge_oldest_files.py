#!/usr/bin/python3
import traceback
from pathlib import Path
from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r"""
---
module: purge_oldest_files

short_description: Remove all but the N newest files from a directory

options:
    path:
        description: The directory to operate on
        required: true
        type: path
    keep:
        description: The number of newest files to keep
        required: true
        type: int
"""


def main():
    module = AnsibleModule(
        argument_spec={
            "path": {"required": True, "type": "path"},
            "keep": {"required": True, "type": "int"},
        },
        supports_check_mode=True,
    )
    path = Path(module.params["path"])
    keep = module.params["keep"]
    changed = False
    try:
        files = [p for p in path.iterdir() if p.is_file()]
        if len(files) > keep:
            changed = True
            if not module.check_mode:
                files.sort(key=lambda p: p.stat().st_mtime)
                for p in files[:-keep]:
                    p.unlink()
    except Exception:
        module.fail_json(msg=traceback.format_exc())
    module.exit_json(changed=changed)

if __name__ == "__main__":
    main()
