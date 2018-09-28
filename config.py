from sqlalchemy.engine.url import URL

SQLALCHEMY_DATABASE_URI = str(URL(
    drivername = "postgresql",
    host       = "localhost",
    port       = 6000,
    database   = "wheelodex",
    username   = "wheelodex",
    password   = "wheelodex",
))

# Don't download anything above this size
WHEELODEX_MAX_WHEEL_SIZE = 1 << 20  # 1 MB
