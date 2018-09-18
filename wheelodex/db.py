from   datetime                   import datetime, timezone
import sqlalchemy as S
from   sqlalchemy.ext.declarative import declarative_base
from   sqlalchemy.orm             import sessionmaker
from   sqlalchemy_utils           import JSONType
from   .                          import __version__

Base = declarative_base()

class WheelDatabase:
    def __init__(self, dburl_params):
        self.engine = S.create_engine(S.engine.url.URL(**dburl_params))
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def __enter__(self):
        self.session.begin_nested()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        return False

    @property
    def serial(self):
        # Serial ID of the last seen PyPI event
        ps = self.session.query(PyPISerial).one_or_none()
        return ps and ps.serial

    @serial.setter
    def serial(self, value):
        ps = self.session.query(PyPISerial).one_or_none()
        if ps is None:
            self.session.add(PyPISerial(serial=value))
        else:
            ps.serial = max(ps.serial, value)

    def queue_wheel(self, whl: 'QueuedWheel', serial=None, force=False):
        if self.session.query(QueuedWheel)\
                       .filter(QueuedWheel.filename == whl.filename)\
                       .one_or_none() is None:
            if force or self.session.query(Wheel)\
                                    .filter(Wheel.filename == whl.filename)\
                                    .one_or_none() is None:
                self.session.add(whl)
        if serial is not None:
            self.serial = serial

    def unqueue_wheel(self, filename):
        if isinstance(filename, QueuedWheel):
            self.session.delete(filename)
        else:
            self.session.query(QueuedWheel)\
                        .filter(QueuedWheel.filename == filename)\
                        .delete()

    def iterqueue(self):  # -> 'Iterator[QueuedWheel]'
        ### Would leaving off the ".all()" give an iterable that plays well
        ### with unqueue_wheel()?
        return self.session.query(QueuedWheel).all()

    def add_wheel_entry(self, about):
        self.session.add(Wheel.from_data(about))

    def remove_wheel(self, filename, serial=None):
        # Remove the given wheel from the database and wheel queue
        self.unqueue_wheel(filename)
        self.session.query(Wheel)\
                    .filter(Wheel.filename == filename)\
                    .update({Wheel.active: False})
        if serial is not None:
            self.serial = serial

    def remove_version(self, project, version, serial=None):
        # Delete all wheels for the given release from the database and wheel
        # queue
        self.session.query(QueuedWheel)\
                    .filter(QueuedWheel.project == project)\
                    .filter(QueuedWheel.version == version)\
                    .delete()
        self.session.query(Wheel)\
                    .filter(Wheel.project == project)\
                    .filter(Wheel.version == version)\
                    .update({Wheel.active: False})
        if serial is not None:
            self.serial = serial

    def remove_project(self, project, serial=None):
        # Delete all wheels for the given project from the database and wheel
        # queue
        self.session.query(QueuedWheel)\
                    .filter(QueuedWheel.project == project)\
                    .delete()
        self.session.query(Wheel)\
                    .filter(Wheel.project == project)\
                    .update({Wheel.active: False})
        if serial is not None:
            self.serial = serial

    def queue_error(self, queued_wheel, errmsg):
        self.session.add(ProcessingError.from_queued_wheel(
            queued_wheel,
            errmsg,
            datetime.now(timezone.utc),
            __version__,
        ))


class QueuedWheel(Base):
    __tablename__ = 'queued_wheels'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    filename = S.Column(S.Unicode(2048), nullable=False, unique=True)
    url      = S.Column(S.Unicode(2048), nullable=False)
    project  = S.Column(S.Unicode(2048), nullable=False)
    version  = S.Column(S.Unicode(2048), nullable=False)
    size     = S.Column(S.Integer, nullable=False)
    md5      = S.Column(S.Unicode(32), nullable=True)
    sha256   = S.Column(S.Unicode(64), nullable=True)
    uploaded = S.Column(S.Unicode(32), nullable=False)


class PyPISerial(Base):
    __tablename__ = 'pypi_serial'

    id     = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    serial = S.Column(S.Integer, nullable=False)


class ProcessingError(Base):
    __tablename__ = 'processing_errors'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    filename = S.Column(S.Unicode(2048), nullable=False)
    url      = S.Column(S.Unicode(2048), nullable=False)
    project  = S.Column(S.Unicode(2048), nullable=False)
    version  = S.Column(S.Unicode(2048), nullable=False)
    size     = S.Column(S.Integer, nullable=False)
    md5      = S.Column(S.Unicode(32), nullable=True)
    sha256   = S.Column(S.Unicode(64), nullable=True)
    uploaded = S.Column(S.Unicode(32), nullable=False)

    errmsg            = S.Column(S.Unicode(65535), nullable=False)
    timestamp         = S.Column(S.DateTime(timezone=True), nullable=False)
    wheelodex_version = S.Column(S.Unicode(32), nullable=False)

    @classmethod
    def from_queued_wheel(cls, qw, errmsg, timestamp, wheelodex_version):
        return cls(
            filename = qw.filename,
            url      = qw.url,
            project  = qw.project,
            version  = qw.version,
            size     = qw.size,
            md5      = qw.md5,
            sha256   = qw.sha256,
            uploaded = qw.uploaded,
            errmsg            = errmsg,
            timestamp         = timestamp,
            wheelodex_version = wheelodex_version,
        )

    def to_queued_wheel(self):
        return QueuedWheel(
            filename = self.filename,
            url      = self.url,
            project  = self.project,
            version  = self.version,
            size     = self.size,
            md5      = self.md5,
            sha256   = self.sha256,
            uploaded = self.uploaded,
        )


class Wheel(Base):
    __tablename__ = 'wheels'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    project  = S.Column(S.Unicode(2048), nullable=False)
    version  = S.Column(S.Unicode(2048), nullable=False)
    filename = S.Column(S.Unicode(2048), nullable=False, unique=True)
    data     = S.Column(JSONType, nullable=False)
    active   = S.Column(S.Boolean, nullable=False, default=True)

    @classmethod
    def from_data(cls, data):
        return cls(
            project  = data["project"],
            version  = data["version"],
            filename = data["filename"],
            data     = data,
            active   = True,
        )
