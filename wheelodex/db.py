from   datetime                   import datetime, timezone
from   typing                     import Optional, Union
from   packaging.utils            import canonicalize_name as normalize, \
                                         canonicalize_version as normversion
import sqlalchemy as S
from   sqlalchemy.ext.declarative import declarative_base
from   sqlalchemy.orm             import backref, relationship, sessionmaker
from   sqlalchemy_utils           import JSONType
from   .                          import __version__

Base = declarative_base()

class WheelDatabase:
    def __init__(self, dburl_params):
        self.engine = S.create_engine(S.engine.url.URL(**dburl_params))
        Base.metadata.create_all(self.engine)
        self.session = None

    def __enter__(self):
        assert self.session is None, \
            'WheelDatabase context manager is not reentrant'
        self.session = sessionmaker(bind=self.engine)()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()
        self.session = None
        return False

    @property
    def serial(self) -> Optional[int]:
        # Serial ID of the last seen PyPI event
        ps = self.session.query(PyPISerial).one_or_none()
        return ps and ps.serial

    @serial.setter
    def serial(self, value: int):
        ps = self.session.query(PyPISerial).one_or_none()
        if ps is None:
            self.session.add(PyPISerial(serial=value))
        else:
            ps.serial = max(ps.serial, value)

    def add_wheel(self, wheel: 'Wheel'):
        whl = self.session.query(Wheel)\
                          .filter(Wheel.filename == wheel.filename)\
                          .one_or_none()
        if whl is None:
            self.session.add(wheel)
        else:
            whl.queued = wheel.queued

    def unqueue_wheel(self, whl: Union[str, 'Wheel']):
        if isinstance(whl, Wheel):
            whl.queued = False
        else:
            self.session.query(Wheel)\
                        .filter(Wheel.filename == whl)\
                        .update({Wheel.queued: False})

    def iterqueue(self) -> ['Wheel']:
        ### Would leaving off the ".all()" give an iterable that plays well
        ### with unqueue_wheel()?
        return self.session.query(Wheel)\
                           .filter(Wheel.queued == True)\
                           .all()  # noqa: E712

    def remove_wheel(self, filename: str):
        self.session.query(Wheel).filter(Wheel.filename == filename).delete()

    def add_wheel_data(self, wheel: 'Wheel', raw_data: dict):
        wheel.data = WheelData.from_raw_data(self.session, raw_data)

    def add_project(self, name: str):
        """
        Create a `Project` with the given name and return it.  If there already
        exists a project with the same name (after normalization), do nothing
        and return that instead.
        """
        return Project.from_name(self.session, name)

    def get_project(self, name: str):
        return self.session.query(Project)\
                           .filter(Project.name == normalize(name))\
                           .one_or_none()

    def remove_project(self, project: str):
        # This deletes the project's versions (and thus also wheels) but leaves
        # the project entry in place in case it's still referenced as a
        # dependency of other wheels.
        #
        # Note that this filters by PyPI project, not by wheel filename
        # project, as this method is meant to be called in response to "remove"
        # events in the PyPI changelog.
        ### TODO: Look into doing this as a JOIN + DELETE of some sort
        p = self.get_project(project)
        if p is not None:
            self.session.query(Version).filter(Version.project == p).delete()

    def add_version(self, project: Union[str, 'Project'], version: str):
        """
        Create a `Version` with the given project & version string and return
        it.  If there already exists a version with the same details, do
        nothing and return that instead.
        """
        if isinstance(project, str):
            project = self.add_project(project)
        return Version.from_version(self.session, project, version)

    def get_version(self, project: Union[str, 'Project'], version: str):
        if isinstance(project, str):
            project = self.get_project(project)
        if project is None:
            return None
        return self.session.query(Version)\
                           .filter(Version.project == project)\
                           .filter(Version.name == normversion(version))\
                           .one_or_none()

    def remove_version(self, project: str, version: str):
        # Note that this filters by PyPI project & version, not by wheel
        # filename project & version, as this method is meant to be called in
        # response to "remove" events in the PyPI changelog.
        self.session.query(Version)\
                    .filter(Version.project.name == normalize(project))\
                    .filter(Version.name == normversion(version))\
                    .delete()
        ### TODO: If the version is the project's latest_version, set
        ### latest_version to next latest

    def add_wheel_error(self, wheel: 'Wheel', errmsg: str):
        wheel.errors.append(ProcessingError(
            errmsg            = errmsg,
            timestamp         = datetime.now(timezone.utc),
            wheelodex_version = __version__,
        ))


class PyPISerial(Base):
    __tablename__ = 'pypi_serial'

    id     = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    serial = S.Column(S.Integer, nullable=False)


class Project(Base):
    __tablename__ = 'projects'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    #: The project's normalized name
    name            = S.Column(S.Unicode(2048), nullable=False, unique=True)
    #: The preferred non-normalized form of the project's name
    display_name    = S.Column(S.Unicode(2048), nullable=False, unique=True)
    ### TODO: Configure this column so that it's set to NULL when the Version
    ### is deleted:
    latest_version_id = S.Column(S.Integer, S.ForeignKey('versions.id'),
                                 nullable=True, default=None)
    latest_version = relationship('Version', foreign_keys=[latest_version_id])
    ### TODO: Configure this column so that it's set to NULL when the Wheel is
    ### deleted:
    latest_wheel_id = S.Column(S.Integer, S.ForeignKey('wheels.id'),
                               nullable=True, default=None)
    latest_wheel    = relationship('Wheel')

    @classmethod
    def from_name(cls, session, name: str):
        proj = session.query(cls).filter(cls.name == normalize(name))\
                                 .one_or_none()
        if proj is None:
            proj = cls(name=normalize(name), display_name=name)
            session.add(proj)
        return proj


class Version(Base):
    __tablename__ = 'versions'
    __table_args__ = (S.UniqueConstraint('project_id', 'name'),)

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    project_id = S.Column(S.Integer,S.ForeignKey('projects.id'),nullable=False)
    project = relationship('Project', backref='versions', foreign_keys=[project_id])
    #: The normalized version string
    name = S.Column(S.Unicode(2048), nullable=False)
    #: The preferred non-normalized version string
    display_name = S.Column(S.Unicode(2048), nullable=False)

    @classmethod
    def from_version(cls, session, project: Project, v: str):
        vnorm = normversion(v)
        vobj = session.query(cls).filter(cls.project == project)\
                                 .filter(cls.name == vnorm)\
                                 .one_or_none()
        if vobj is None:
            vobj = cls(project=project, name=vnorm, display_name=v)
            session.add(vobj)
        return vobj


class Wheel(Base):
    """
    A table of *all* wheels available on PyPI, even ones we're not storing data
    for.  We store all the wheels so that, if we ever decide to go back and
    analyze wheels we declined to analyze earlier, we don't have to spend hours
    scraping the entire XML-RPC API to find them.  Also, the table provides
    statistics on wheels that can be useful for deciding whether to go back and
    analyze more wheels in the first place.
    """

    __tablename__ = 'wheels'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    filename = S.Column(S.Unicode(2048), nullable=False, unique=True)
    url      = S.Column(S.Unicode(2048), nullable=False)
    version_id = S.Column(S.Integer,S.ForeignKey('versions.id'),nullable=False)
    version  = relationship('Version', backref='wheels')
    size     = S.Column(S.Integer, nullable=False)
    md5      = S.Column(S.Unicode(32), nullable=True)
    sha256   = S.Column(S.Unicode(64), nullable=True)
    uploaded = S.Column(S.Unicode(32), nullable=False)
    queued   = S.Column(S.Boolean, nullable=False)


class ProcessingError(Base):
    __tablename__ = 'processing_errors'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    wheel_id  = S.Column(S.Integer, S.ForeignKey('wheels.id'), nullable=False)
    wheel     = relationship('Wheel', backref='errors')
    errmsg    = S.Column(S.Unicode(65535), nullable=False)
    timestamp = S.Column(S.DateTime(timezone=True), nullable=False)
    wheelodex_version = S.Column(S.Unicode(32), nullable=False)


dependency_tbl = S.Table('dependency_tbl', Base.metadata,
    S.Column('wheel_data_id', S.Integer, S.ForeignKey('wheel_data.id'), nullable=False),
    S.Column('project_id', S.Integer, S.ForeignKey('projects.id'), nullable=False),
    S.UniqueConstraint('wheel_data_id', 'project_id'),
)


class WheelData(Base):
    __tablename__ = 'wheel_data'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    wheel_id  = S.Column(S.Integer, S.ForeignKey('wheels.id'), nullable=False,
                         unique=True)
    wheel     = relationship('Wheel', backref=backref('data', uselist=False))
    raw_data  = S.Column(JSONType, nullable=False)
    #: The project name as extracted from the wheel filename.  This may differ
    #: from the project name as reported on PyPI, even after normalization.
    project   = S.Column(S.Unicode(2048), nullable=False)
    version   = S.Column(S.Unicode(2048), nullable=False)
    #: The time at which the raw data was extracted from the wheel and added to
    #: the database
    processed = S.Column(S.DateTime(timezone=True), nullable=False)
    #: The version of `wheelodex` under which the WheelData's columns and
    #: relations were filled in
    wheelodex_version = S.Column(S.Unicode(32), nullable=False)
    dependencies = relationship('Project', secondary=dependency_tbl,
                                backref='rdepends')

    @classmethod
    def from_raw_data(cls, session, raw_data: dict):
        return cls(
            raw_data  = raw_data,
            processed = datetime.now(timezone.utc),
            **cls.parse_raw_data(session, raw_data),
        )

    @staticmethod
    def parse_raw_data(session, raw_data: dict):
        return {
            "wheelodex_version": __version__,
            "project": raw_data["project"],
            "version": raw_data["version"],
            "entry_points": [
                EntryPoint(
                    group=EntryPointGroup.from_name(session, group),
                    name=e,
                )
                for group, eps in raw_data["dist_info"].get("entry_points", {})
                                                       .items()
                for e in eps
            ],
            "dependencies": [
                Project.from_name(session, p)
                for p in raw_data["derived"]["dependencies"]
            ],
        }

    def update_structure(self, session):
        """
        Update the `WheelData` and its subobjects for the current database
        schema
        """
        ### TODO: For subobjects like EntryPoints, try to eliminate replacing
        ### unchanged subobjects with equal subobjects with new IDs every time
        ### this method is called
        for k,v in self.parse_raw_data(session, self.raw_data):
            setattr(self, k, v)


class EntryPointGroup(Base):
    __tablename__ = 'entry_point_groups'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    name        = S.Column(S.Unicode(2048), nullable=False, unique=True)
    description = S.Column(S.Unicode(65535), nullable=True, default=None)

    @classmethod
    def from_name(cls, session, name: str):
        epg = session.query(cls).filter(cls.name == name).one_or_none()
        if epg is None:
            epg = cls(name=name)
            session.add(epg)
        return epg


class EntryPoint(Base):
    __tablename__ = 'entry_points'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    wheel_data_id = S.Column(S.Integer, S.ForeignKey('wheel_data.id'),
                             nullable=False)
    wheel_data    = relationship('WheelData', backref='entry_points')
    group_id      = S.Column(S.Integer, S.ForeignKey('entry_point_groups.id'),
                             nullable=False)
    group         = relationship('EntryPointGroup')
    name          = S.Column(S.Unicode(2048), nullable=False)
