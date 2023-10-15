from sqlalchemy import URL

SQLALCHEMY_DATABASE_URI = URL.create(
    drivername = "postgresql+psycopg",
    host       = "localhost",
    port       = 5432,
    database   = {{"%r"|format(dbname)}},
    username   = {{"%r"|format(dbuser)}},
    password   = {{"%r"|format(dbpass)}},
)

{% for key, value in config_options.items() %}
{{key}} = {{"%r"|format(value)}}
{% endfor %}
