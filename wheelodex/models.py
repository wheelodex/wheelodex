from   datetime         import datetime, timezone
from   flask_sqlalchemy import SQLAlchemy
from   packaging.utils  import canonicalize_name as normalize
import sqlalchemy as S
from   sqlalchemy.orm   import backref, object_session, relationship
from   sqlalchemy_utils import JSONType
from   .                import __version__
from   .util            import reprify

db = SQLAlchemy()
Base = db.Model

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
    def from_name(cls, name: str):
        proj = cls.query.filter(cls.name == normalize(name)).one_or_none()
        if proj is None:
            proj = cls(name=normalize(name), display_name=name)
            db.session.add(proj)
        return proj

    @property
    def latest_version(self):
        return object_session(self).query(Version)\
                                   .filter(Version.project == self)\
                                   .order_by(Version.ordering.desc())\
                                   .first()

    @property
    def preferred_wheel(self):
        return object_session(self).query(Wheel)\
                                   .join(Version)\
                                   .filter(Version.project == self)\
                                   .filter(Wheel.data.has())\
                                   .order_by(Version.ordering.desc())\
                                   .order_by(Wheel.ordering.desc())\
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
    #: version is added to the project with `add_version()`.
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
    #: The index of this wheel when all wheels for the version are sorted by
    #: applying `wheel_sort_key()` to their filenames.  This column is set
    #: every time a new wheel is added to the version with `add_wheel()`.
    ordering = S.Column(S.Integer, nullable=False, default=0)

    def __repr__(self):
        return reprify(self, ['filename'])

    @property
    def project(self):
        return self.version.project

    def set_data(self, raw_data: dict):
        ### TODO: This errors if `self.data` is already non-None (because then
        ### there are temporarily two WheelData objects with the same
        ### `wheel_id`).  Fix this.
        self.data = WheelData.from_raw_data(raw_data)

    def add_error(self, errmsg: str):
        self.errors.append(ProcessingError(
            errmsg            = errmsg[-65535:],
            timestamp         = datetime.now(timezone.utc),
            wheelodex_version = __version__,
        ))

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
    def from_raw_data(cls, raw_data: dict):
        return cls(
            raw_data  = raw_data,
            processed = datetime.now(timezone.utc),
            **cls.parse_raw_data(raw_data),
        )

    @staticmethod
    def parse_raw_data(raw_data: dict):
        summary = raw_data["dist_info"].get("metadata", {}).get("summary")
        return {
            "wheelodex_version": __version__,
            "project": raw_data["project"],
            "version": raw_data["version"],
            "entry_points": [
                EntryPoint(group=grobj, name=e)
                for group, eps in raw_data["dist_info"].get("entry_points", {})
                                                       .items()
                for grobj in [EntryPointGroup.from_name(group)]
                for e in eps
            ],
            "dependencies": [
                Project.from_name(p)
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

    def update_structure(self):
        """
        Update the `WheelData` and its subobjects for the current database
        schema
        """
        ### TODO: For subobjects like EntryPoints, try to eliminate replacing
        ### unchanged subobjects with equal subobjects with new IDs every time
        ### this method is called
        for k,v in self.parse_raw_data(self.raw_data):
            setattr(self, k, v)


class EntryPointGroup(Base):
    __tablename__ = 'entry_point_groups'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    name        = S.Column(S.Unicode(2048), nullable=False, unique=True)
    description = S.Column(S.Unicode(65535), nullable=True, default=None)

    def __repr__(self):
        return reprify(self, ['name'])

    @classmethod
    def from_name(cls, name: str):
        epg = cls.query.filter(cls.name == name).one_or_none()
        if epg is None:
            epg = cls(name=name)
            db.session.add(epg)
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
        return reprify(self, 'wheel_data group name'.split())


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
