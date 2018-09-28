from   datetime                   import datetime, timezone
from   typing                     import Optional, Union
from   flask_sqlalchemy           import SQLAlchemy
from   packaging.utils            import canonicalize_name as normalize, \
                                         canonicalize_version as normversion
import sqlalchemy as S
from   sqlalchemy.orm             import backref, object_session, relationship
from   sqlalchemy_utils           import JSONType
from   .                          import __version__
from   .util                      import reprify, version_sort_key

db = SQLAlchemy()
Base = db.Model

class WheelDatabase:
    def __init__(self):
        db.create_all()
        self.session = None

    def __enter__(self):
        assert self.session is None, \
            'WheelDatabase context manager is not reentrant'
        self.session = db.session
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

    def add_wheel(self, version: 'Version', filename, url, size, md5, sha256,
                  uploaded):
        whl = self.session.query(Wheel)\
                          .filter(Wheel.filename == filename)\
                          .one_or_none()
        if whl is None:
            whl = Wheel(
                version  = version,
                filename = filename,
                url      = url,
                size     = size,
                md5      = md5,
                sha256   = sha256,
                uploaded = uploaded,
            )
            self.session.add(whl)
        return whl

    def iterqueue(self) -> ['Wheel']:
        ### Would leaving off the ".all()" give an iterable that plays well
        ### with wheels being given data concurrently?
        return self.session.query(Wheel)\
                           .filter(~Wheel.data.has())\
                           .filter(~Wheel.errors.any())\
                           .all()

    def remove_wheel(self, filename: str):
        self.session.query(Wheel).filter(Wheel.filename == filename).delete()

    def add_wheel_data(self, wheel: 'Wheel', raw_data: dict):
        ### TODO: This errors if `wheel.data` is already non-None (because then
        ### there are temporarily two WheelData objects with the same
        ### `wheel_id`).  Fix this.
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

    def get_all_projects(self):
        return self.session.query(Project).all()

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
        vnorm = normversion(version)
        v = self.session.query(Version).filter(Version.project == project)\
                                       .filter(Version.name == vnorm)\
                                       .one_or_none()
        if v is None:
            v = Version(project=project, name=vnorm, display_name=version)
            self.session.add(v)
            for i,u in enumerate(
                ### TODO: Is `project.versions` safe to use when some of its
                ### elements may have been deleted earlier in the transaction?
                sorted(project.versions, key=lambda x: version_sort_key(x.name))
            ):
                u.ordering = i
        return v

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
        ### TODO: Look into doing this as a JOIN + DELETE of some sort
        p = self.get_project(project)
        if p is not None:
            self.session.query(Version)\
                        .filter(Version.project == p)\
                        .filter(Version.name == normversion(version))\
                        .delete()

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

    def __repr__(self):
        return reprify(self, ['serial'])


class Project(Base):
    __tablename__ = 'projects'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    #: The project's normalized name
    name         = S.Column(S.Unicode(2048), nullable=False, unique=True)
    #: The preferred non-normalized form of the project's name
    display_name = S.Column(S.Unicode(2048), nullable=False, unique=True)

    def __repr__(self):
        return reprify(self, 'name display_name'.split())

    @classmethod
    def from_name(cls, session, name: str):
        proj = session.query(cls).filter(cls.name == normalize(name))\
                                 .one_or_none()
        if proj is None:
            proj = cls(name=normalize(name), display_name=name)
            session.add(proj)
        return proj

    @property
    def latest_version(self):
        return object_session(self).query(Version)\
                                   .filter(Version.project == self)\
                                   .order_by(Version.ordering.desc())\
                                   .first()


class Version(Base):
    __tablename__ = 'versions'
    __table_args__ = (S.UniqueConstraint('project_id', 'name'),)

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    project_id = S.Column(
        S.Integer,
        S.ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
    )
    project = relationship(
        'Project',
        backref=backref('versions', cascade='all, delete-orphan',
                        passive_deletes=True),
    )
    #: The normalized version string
    name = S.Column(S.Unicode(2048), nullable=False)
    #: The preferred non-normalized version string
    display_name = S.Column(S.Unicode(2048), nullable=False)
    #: The index of this version when all versions for the project are sorted
    #: in PEP 440 order with prereleases at the bottom.  (The latest version
    #: has the highest `ordering` value.)  This column is set every time a new
    #: version is added to the project with WheelDatabase.add_version().
    ordering = S.Column(S.Integer, nullable=False, default=0)

    def __repr__(self):
        return reprify(self, 'project name display_name ordering'.split())


class Wheel(Base):
    __tablename__ = 'wheels'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    filename = S.Column(S.Unicode(2048), nullable=False, unique=True)
    url      = S.Column(S.Unicode(2048), nullable=False)
    version_id = S.Column(
        S.Integer,
        S.ForeignKey('versions.id', ondelete='CASCADE'),
        nullable=False,
    )
    version  = relationship(
        'Version',
        backref=backref('wheels', cascade='all, delete-orphan',
                        passive_deletes=True),
    )
    size     = S.Column(S.Integer, nullable=False)
    md5      = S.Column(S.Unicode(32), nullable=True)
    sha256   = S.Column(S.Unicode(64), nullable=True)
    uploaded = S.Column(S.Unicode(32), nullable=False)

    def __repr__(self):
        return reprify(self, 'filename'.split())

    @property
    def project(self):
        return self.version.project

    def as_json(self):
        about = {
            "pypi": {
                "filename": self.filename,
                "url": self.url,
                "project": self.project.display_name,
                "version": self.version.display_name,
                "size": self.size,
                "md5": self.md5,
                "sha256": self.sha256,
                "uploaded": self.uploaded,
            },
        }
        if self.data is not None:
            about["data"] = self.data.raw_data
            about["wheelodex"] = {
                "processed": str(self.data.processed),
                "wheelodex_version": self.data.wheelodex_version,
            }
        return about


class ProcessingError(Base):
    __tablename__ = 'processing_errors'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    wheel_id  = S.Column(
        S.Integer,
        S.ForeignKey('wheels.id', ondelete='CASCADE'),
        nullable=False,
    )
    wheel     = relationship(
        'Wheel',
        backref=backref('errors', cascade='all, delete-orphan',
                        passive_deletes=True),
    )
    errmsg    = S.Column(S.Unicode(65535), nullable=False)
    timestamp = S.Column(S.DateTime(timezone=True), nullable=False)
    wheelodex_version = S.Column(S.Unicode(32), nullable=False)


dependency_tbl = S.Table('dependency_tbl', Base.metadata,
    S.Column(
        'wheel_data_id',
        S.Integer,
        S.ForeignKey('wheel_data.id', ondelete='CASCADE'),
        nullable=False,
    ),
    S.Column(
        'project_id',
        S.Integer,
        S.ForeignKey('projects.id', ondelete='RESTRICT'),
        nullable=False,
    ),
    S.UniqueConstraint('wheel_data_id', 'project_id'),
)


class WheelData(Base):
    __tablename__ = 'wheel_data'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    wheel_id  = S.Column(
        S.Integer,
        S.ForeignKey('wheels.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    wheel     = relationship(
        'Wheel',
        backref=backref('data', uselist=False, cascade='all, delete-orphan',
                        passive_deletes=True),
    )
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
    ### TODO: What are the right `cascade` and `passive_deletes` settings for
    ### this relationship?
    dependencies = relationship('Project', secondary=dependency_tbl,
                                backref='rdepends')
    summary   = S.Column(S.Unicode(2048), nullable=True)
    verified  = S.Column(S.Boolean, nullable=False)

    @classmethod
    def from_raw_data(cls, session, raw_data: dict):
        return cls(
            raw_data  = raw_data,
            processed = datetime.now(timezone.utc),
            **cls.parse_raw_data(session, raw_data),
        )

    @staticmethod
    def parse_raw_data(session, raw_data: dict):
        summary = raw_data["dist_info"].get("metadata", {}).get("summary")
        return {
            "wheelodex_version": __version__,
            "project": raw_data["project"],
            "version": raw_data["version"],
            "entry_points": [
                EntryPoint(group=grobj, name=e)
                for group, eps in raw_data["dist_info"].get("entry_points", {})
                                                       .items()
                for grobj in [EntryPointGroup.from_name(session, group)]
                for e in eps
            ],
            "dependencies": [
                Project.from_name(session, p)
                for p in raw_data["derived"]["dependencies"]
            ],
            "summary": summary[:2048] if summary is not None else None,
            "verified": raw_data["verifies"],
            "keywords": [
                Keyword(name=k) for k in raw_data["derived"]["keywords"]
            ],
            "files": [
                File(
                    path=f["path"],
                    size=f["size"],
                    sha256_base64=f["digests"].get("sha256"),
                ) for f in raw_data["dist_info"].get("record", [])
            ],
            "modules": [Module(name=m) for m in raw_data["derived"]["modules"]],
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

    def __repr__(self):
        return reprify(self, 'name')

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
    wheel_data_id = S.Column(
        S.Integer,
        S.ForeignKey('wheel_data.id', ondelete='CASCADE'),
        nullable=False,
    )
    wheel_data    = relationship(
        'WheelData',
        backref=backref('entry_points', cascade='all, delete-orphan',
                        passive_deletes=True),
    )
    group_id      = S.Column(
        S.Integer,
        S.ForeignKey('entry_point_groups.id', ondelete='RESTRICT'),
        nullable=False,
    )
    group         = relationship('EntryPointGroup')
    name          = S.Column(S.Unicode(2048), nullable=False)

    def __repr__(self):
        return reprify(self, 'wheel_data group name')


class File(Base):
    __tablename__ = 'files'
    __table_args__ = (S.UniqueConstraint('wheel_data_id', 'path'),)

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    wheel_data_id = S.Column(
        S.Integer,
        S.ForeignKey('wheel_data.id', ondelete='CASCADE'),
        nullable=False,
    )
    wheel_data    = relationship(
        'WheelData',
        backref=backref('files', cascade='all, delete-orphan',
                        passive_deletes=True),
    )
    path          = S.Column(S.Unicode(2048), nullable=False)
    size          = S.Column(S.Integer, nullable=True)
    sha256_base64 = S.Column(S.Unicode(43), nullable=True)


class Module(Base):
    __tablename__ = 'modules'
    __table_args__ = (S.UniqueConstraint('wheel_data_id', 'name'),)

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    wheel_data_id = S.Column(
        S.Integer,
        S.ForeignKey('wheel_data.id', ondelete='CASCADE'),
        nullable=False,
    )
    wheel_data    = relationship(
        'WheelData',
        backref=backref('modules', cascade='all, delete-orphan',
                        passive_deletes=True),
    )
    name          = S.Column(S.Unicode(2048), nullable=False)


class Keyword(Base):
    __tablename__ = 'keywords'
    #__table_args__ = (S.UniqueConstraint('wheel_data_id', 'name'),)

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    wheel_data_id = S.Column(
        S.Integer,
        S.ForeignKey('wheel_data.id', ondelete='CASCADE'),
        nullable=False,
    )
    wheel_data    = relationship(
        'WheelData',
        backref=backref('keywords', cascade='all, delete-orphan',
                        passive_deletes=True),
    )
    name          = S.Column(S.Unicode(2048), nullable=False)
