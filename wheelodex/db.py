import sqlalchemy as S
from   sqlalchemy.ext.declarative import declarative_base
from   sqlalchemy.orm             import sessionmaker
#from   sqlalchemy_utils           import JSONType

Base = declarative_base()

class WheelDatabase:
    def __init__(self, dburl_params):
        self.engine = S.create_engine(S.engine.url.URL(**dburl_params))
        Base.metadata.create_all(self.engine)
        self.session = None

    def __enter__(self):
        self.session = sessionmaker(bind=self.engine)()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()
        return False

    def queue_wheel(self, whl: 'QueuedWheel', serial=None, force=False):
        if self.session.query(QueuedWheel)\
                       .filter(QueuedWheel.filename == whl.filename)\
                       .one_or_none() is None:
            ### TODO: If the wheel is already in the database and `force` is
            ### false, don't add to the queue
            self.session.add(whl)
        if serial is not None:
            self.serial = serial

    def remove_wheel(self, filename, serial=None):
        # Remove the given wheel from the database and wheel queue
        self.unqueue_wheel(filename)
        ### TODO: Remove wheel from main database
        if serial is not None:
            self.serial = serial

    def unqueue_wheel(self, filename):
        if isinstance(filename, QueuedWheel):
            self.session.delete(filename)
        else:
            self.session.query(QueuedWheel)\
                        .filter(QueuedWheel.filename == filename)\
                        .delete()

    def remove_version(self, project, version, serial=None):
        # Delete all wheels for the given release from the database and wheel
        # queue
        raise NotImplementedError

    def remove_project(self, project, serial=None):
        # Delete all wheels for the given project from the database and wheel
        # queue
        raise NotImplementedError

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

    def add_wheel_entry(self, about):
        raise NotImplementedError

    def iterqueue(self) -> 'Iterator[QueuedWheel]':
        ### Make sure this interacts well with unqueue_wheel()
        raise NotImplementedError

    def queue_error(self, queued_wheel, errmsg):
        raise NotImplementedError


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
