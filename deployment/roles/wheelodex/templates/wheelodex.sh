#!/bin/bash
WHEELODEX_CONFIG={{wheelodex_config_file|quote}} {{wheelodex_venv_path|quote}}/bin/python -m wheelodex "$@"
