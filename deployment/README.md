Requirements
------------

On the local/control machine:

- Ansible v8.5+ (full package, not just `ansible-core`)

On the remote/managed machine:

- Ubuntu Jammy or higher
- Python 3 at `/usr/bin/python3`


Variables
---------

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `wheelodex_dbname` | `wheelodex` | PostgreSQL database to create & use for Wheelodex |
| `wheelodex_dbuser` | `wheelodex` | PostgreSQL user account that will own the database and that Wheelodex will connect to PostgreSQL as |
| `wheelodex_dbpass` | —  | **Required**; password for the PostgreSQL user account |
| `wheelodex_dbdump_path` | `/var/backups/wheelodex/postgres` | The directory in which to create backups of the PostgreSQL database |
| `wheelodex_user` | `wheelodex` | Dedicated user account that will be used to store & run Wheelodex |
| `wheelodex_venv_path` | `/home/{{user}}/virtualenv` | Path at which to create the virtualenv in which `wheelodex` will be installed |
| `wheelodex_purge_venv` | `false` | Whether to delete and recreate the virtualenv from scratch |
| `wheelodex_upgrade_pip` | `false` | Whether to upgrade the dedicated user's versions of `pip` and `virtualenv` |
| `wheelodex_config_file` | `/home/{{user}}/config.py` | Path at which to place Wheelodex's config file |
| `wheelodex_wsgi_file` | `/home/{{user}}/wsgi.py` | Path at which to place Wheelodex's WSGI file |
| `wheelodex_log_path` | `/home/{{user}}/logs` | Directory in which to store Wheelodex's statistics logs |
| `wheelodex_wheel` | — | Path to the `wheelodex` wheel on the local machine; may be left undefined to skip installation |
| `wheelodex_extras` | `'[postgres]'` | Extras of the wheel to install |
| `wheelodex_config_options` | `{}` | A `dict` of Wheelodex configuration values |
| `wheelodex_server_names` | — | **Required**; a list of DNS names to which the server responds.  The first element is the "canonical" name, and HTTP requests to the other elements will be redirected to it. |
| `wheelodex_certname` | `wheelodex` | Name of the SSL certificate created & managed by Certbot |
| `wheelodex_certbot_email` | — | **Required**; e-mail address to provide to Certbot when creating the SSL certificate |
| `wheelodex_uwsgi_socket` | `/tmp/wheelodex.sock` | Path of socket that uWSGI and Nginx will use to communicate |
| `wheelodex_uwsgi_processes` | `4` | Number of uWSGI processes to spawn |
| `wheelodex_uwsgi_threads` | `2` | Number of threads per uWSGI process to spawn |
| `wheelodex_errmail_from_addr` | — | **Required**; e-mail address from which to send e-mails about failed scheduled tasks |
| `wheelodex_errmail_to_addr` | — | **Required**; e-mail address to which to send e-mails about failed scheduled tasks |
| `wheelodex_mailgun_smtp_username` | — | **Required**; Mailgun SMTP username |
| `wheelodex_mailgun_smtp_password` | — | **Required**; Mailgun SMTP password |
| `wheelodex_register_wheels_per_day` | `3` | How many times per day to run the `register-wheels` service |
| `wheelodex_register_wheels_start` | `0` | The hour of the first run of the day of the `register-wheels` service |
| `wheelodex_process_wheels_per_day` | `1` | How many times per day to run the `process-wheels` service |
| `wheelodex_process_wheels_start` | `6` | The hour of the first run of the day of the `process-wheels` service |

Setup Steps that this Playbook does not Cover
---------------------------------------------
- Provisioning the host
- Assigning the host's DNS
- Setting up SSH access to host
- Creating a dedicated non-root user with sudo privileges and SSH access to use
  for server administration
- Setting the host's locale system-wide to something with UTF-8 encoding (This
  should be redundant in this day & age, and doing it properly involves a
  reboot, so we'd want to keep that out of the playbook)
- Ensuring that Python 3 is installed at `/usr/bin/python3`
- Ensuring that setuptools is installed system-wide for Python 3
