Requirements
------------

On the local/control machine:

- Ansible v2.7+

On the remote/managed machine:

- Ubuntu Bionic (or possibly higher)


Variables
---------

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `dbname` | `wheelodex` | PostgreSQL database to create & use for Wheelodex |
| `dbuser` | `wheelodex` | PostgreSQL user account that will own the database and that Wheelodex will connect to PostgreSQL as |
| `dbpass` | —  | **Required**; password for the PostgreSQL user account |
| `dbdump_path` | `/var/backups/wheelodex/postgres` | The directory in which to create backups of the PostgreSQL database |
| `user` | `wheelodex` | Dedicated user account that will be used to store & run Wheelodex |
| `venv_path` | `/home/{{user}}/virtualenv` | Path at which to create the virtualenv in which `wheelodex` will be installed |
| `purge_venv` | `false` | Whether to delete and recreate the virtualenv from scratch |
| `upgrade_pip` | `false` | Whether to upgrade the dedicated user's versions of `pip` and `virtualenv` |
| `config_file` | `/home/{{user}}/config.py` | Path at which to place Wheelodex's config file |
| `wsgi_file` | `/home/{{user}}/wsgi.py` | Path at which to place Wheelodex's WSGI file |
| `wheelodex_log_path` | `/home/{{user}}/logs` | Directory in which to store Wheelodex's statistics logs |
| `wheel_src` | — | Path to the `wheelodex` wheel on the local machine; may be left undefined to skip installation |
| `extras` | `'[postgres]'` | Extras of the wheel to install |
| `config_options` | `{}` | A `dict` of Wheelodex configuration values |
| `server_names` | — | **Required**; a list of DNS names to which the server responds.  The first element is the "canonical" name, and HTTP requests to the other elements will be redirected to it. |
| `certname` | `wheelodex` | Name of the SSL certificate created & managed by Certbot |
| `certbot_email` | — | **Required**; e-mail address to provide to Certbot when creating the SSL certificate |
| `uwsgi_socket` | `/tmp/wheelodex.sock` | Path of socket that uWSGI and Nginx will use to communicate |
| `uwsgi_processes` | `4` | Number of uWSGI processes to spawn |
| `uwsgi_threads` | `2` | Number of threads per uWSGI process to spawn |
| `errmail_from_addr` | — | **Required**; e-mail address from which to send e-mails about failed scheduled tasks |
| `errmail_to_addr` | — | **Required**; e-mail address to which to send e-mails about failed scheduled tasks |
| `mailgun_smtp_username` | — | **Required**; Mailgun SMTP username |
| `mailgun_smtp_password` | — | **Required**; Mailgun SMTP password |
| `register_wheels_per_day` | `3` | How many times per day to run the `register-wheels` service |
| `register_wheels_start` | `0` | The hour of the first run of the day of the `register-wheels` service |
| `process_wheels_per_day` | `1` | How many times per day to run the `process-wheels` service |
| `process_wheels_start` | `6` | The hour of the first run of the day of the `process-wheels` service |

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
