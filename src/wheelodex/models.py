""" Database classes """

from   datetime         import datetime, timezone
from   itertools        import groupby
from   flask_sqlalchemy import SQLAlchemy
from   packaging.utils  import canonicalize_name as normalize
import sqlalchemy as S
from   sqlalchemy.orm   import backref, relationship
from   sqlalchemy_utils import JSONType
from   wheel_inspect    import __version__ as wheel_inspect_version
from   .                import __version__
from   .util            import reprify

db = SQLAlchemy()
Base = db.Model

class PyPISerial(Base):
    """
    A table for storing the serial ID of the last PyPI event seen.  There
    should never be more than one row in this table.
    """

    __tablename__ = 'pypi_serial'

    id     = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    serial = S.Column(S.Integer, nullable=False)

    def __repr__(self):
        return reprify(self, ['serial'])


class Project(Base):
    """ A PyPI project """

    __tablename__ = 'projects'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    #: The project's normalized name
    name         = S.Column(S.Unicode(2048), nullable=False, unique=True)
    #: The preferred non-normalized form of the project's name
    display_name = S.Column(S.Unicode(2048), nullable=False, unique=True)
    #: A summary of the project taken from its most recently-analyzed wheel.
    #: (The summary is stored here instead of in `WheelData` because storing it
    #: in `WheelData` would mean that listing projects with their summaries
    #: would involve a complicated query that ends up being noticeably too
    #: slow.)
    summary      = S.Column(S.Unicode(2048), nullable=True)
    #: Whether this project has any wheels known to the database
    has_wheels   = S.Column(S.Boolean, default=False, nullable=False)

    def __repr__(self):
        return reprify(self, 'name display_name'.split())

    @classmethod
    def from_name(cls, name: str):
        """
        Construct a `Project` with the given name and return it.  If such a
        project already exists, return that one instead.
        """
        proj = cls.query.filter(cls.name == normalize(name)).one_or_none()
        if proj is None:
            proj = cls(name=normalize(name), display_name=name)
            db.session.add(proj)
        return proj

    @property
    def latest_version(self):
        r"""
        The `Version` for this `Project` with the highest ``ordering`` value,
        or `None` if there are no `Version`\ s
        """
        return Version.query.filter(Version.project == self)\
                            .order_by(Version.ordering.desc())\
                            .first()

    @property
    def preferred_wheel(self):
        """
        The project's "preferred wheel": the highest-ordered wheel with data
        for the highest-ordered version
        """
        return Wheel.query.join(Version)\
                          .filter(Version.project == self)\
                          .filter(Wheel.data.has())\
                          .order_by(Version.ordering.desc())\
                          .order_by(Wheel.ordering.desc())\
                          .first()

    @property
    def best_wheel(self):
        """
        The project's preferred wheel, if it exists (i.e., if any of the
        project's wheels have data); otherwise, the highest-ordered wheel for
        the highest-ordered version
        """
        return Wheel.query.join(Version)\
                          .filter(Version.project == self)\
                          .outerjoin(WheelData)\
                          .order_by(WheelData.id.isnot(None).desc())\
                          .order_by(Version.ordering.desc())\
                          .order_by(Wheel.ordering.desc())\
                          .first()

    def versions_wheels_grid(self):
        r"""
        Returns a "grid" of all of this project's `Wheel`\ s, arranged by
        `Version`.  The return value is a list of pairs in which the first
        element is a `Version`'s ``display_name`` and the second element is a
        list of ``(Wheel, bool)`` pairs listing the wheels for that version and
        whether they have data.  The versions are ordered from highest
        ``ordering`` to lowest, and the `Wheel`\ s within each version are
        ordered from highest ``ordering`` to lowest.  Versions that do not have
        wheels are ignored.
        """
        q = db.session.query(Version.display_name, Wheel, WheelData.id.isnot(None))\
                      .join(Wheel, Version.wheels)\
                      .outerjoin(WheelData)\
                      .filter(Version.project == self)\
                      .order_by(Version.ordering.desc())\
                      .order_by(Wheel.ordering.desc())
        results = []
        for v, ws in groupby(q, lambda r: r[0]):
            results.append((v, [(w,b) for _,w,b in ws]))
        return results


class Version(Base):
    """ A version (a.k.a. release) of a `Project` """

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
    """ A wheel belonging to a `Version` """

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
    uploaded = S.Column(S.DateTime(timezone=True), nullable=False)
    #: The index of this wheel when all wheels for the version are sorted by
    #: applying `wheel_sort_key()` to their filenames.  This column is set
    #: every time a new wheel is added to the version with `add_wheel()`.
    ordering = S.Column(S.Integer, nullable=False, default=0)

    def __repr__(self):
        return reprify(self, ['filename'])

    @property
    def project(self):
        """ The `Project` to which the wheel belongs """
        return self.version.project

    def set_data(self, raw_data: dict):
        """
        Use the results of a call to `inspect_wheel()` to populate this wheel's
        `WheelData`
        """
        ### TODO: This errors if `self.data` is already non-None (because then
        ### there are temporarily two WheelData objects with the same
        ### `wheel_id`).  Fix this.
        self.data = WheelData.from_raw_data(raw_data)
        summary = raw_data["dist_info"].get("metadata", {}).get("summary")
        self.project.summary = summary[:2048] if summary is not None else None

    def add_error(self, errmsg: str):
        """
        Register an error that occurred while processing this wheel for data
        """
        self.errors.append(ProcessingError(
            errmsg            = errmsg[-65535:],
            timestamp         = datetime.now(timezone.utc),
            wheelodex_version = __version__,
            wheel_inspect_version = wheel_inspect_version,
        ))

    def as_json(self):
        """
        Returns a JSONable representation (i.e., a `dict` composed entirely of
        primitive types that can be directly serialized to JSON) of the wheel
        and its data, if any
        """
        about = {
            "pypi": {
                "filename": self.filename,
                "url": self.url,
                "project": self.project.display_name,
                "version": self.version.display_name,
                "size": self.size,
                "md5": self.md5,
                "sha256": self.sha256,
                "uploaded": self.uploaded.isoformat(),
            },
        }
        if self.data is not None:
            about["data"] = self.data.raw_data
            about["wheelodex"] = {
                "processed": self.data.processed.isoformat(),
                "wheel_inspect_version": self.data.wheel_inspect_version,
            }
        if self.errors:
            about["errored"] = True
        return about


class ProcessingError(Base):
    """ An error that occurred while processing a `Wheel` for data """

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
    wheel_inspect_version = S.Column(S.Unicode(32), nullable=True)


class DependencyRelation(Base):
    """
    An association object that maps `WheelData` values to the `Project`\\ s
    listed in their :mailheader:`Requires-Dist` fields
    """

    __tablename__ = 'dependency_tbl'

    wheel_data_id = S.Column(
        S.Integer,
        S.ForeignKey('wheel_data.id', ondelete='CASCADE'),
        nullable=False,
        primary_key=True,
    )

    project_id = S.Column(
        S.Integer,
        S.ForeignKey('projects.id', ondelete='RESTRICT'),
        nullable=False,
        primary_key=True,
    )
    project = relationship('Project', foreign_keys=[project_id])

    #: A redundant reference to the project to which the wheel belongs, stored
    #: here to make some queries faster:
    source_project_id = S.Column(
        S.Integer,
        S.ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
    )


class WheelData(Base):
    """ Information about a `Wheel` produced with `inspect_wheel()` """

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
    #: The time at which the raw data was extracted from the wheel and added to
    #: the database
    processed = S.Column(S.DateTime(timezone=True), nullable=False)
    #: The version of wheel-inspect that produced the ``raw_data``
    wheel_inspect_version = S.Column(S.Unicode(32), nullable=False)
    ### TODO: What are the right `cascade` and `passive_deletes` settings for
    ### this relationship?
    dependency_rels = relationship('DependencyRelation')
    valid     = S.Column(S.Boolean, nullable=False)

    @property
    def dependencies(self):
        return [rel.project for rel in self.dependency_rels]

    @classmethod
    def from_raw_data(cls, raw_data: dict):
        """
        Construct a new `WheelData` object, complete with related objects, from
        the return value of a call to `inspect_wheel()`
        """
        file_paths = {
            # Make this a set because some wheels have duplicate entries in
            # their RECORDs
            f["path"] for f in raw_data["dist_info"].get("record", [])
        }
        project = Project.from_name(raw_data["project"])
        return cls(
            raw_data  = raw_data,
            processed = datetime.now(timezone.utc),
            wheel_inspect_version = wheel_inspect_version,
            entry_points = [
                EntryPoint(group=grobj, name=e)
                for group, eps in raw_data["dist_info"].get("entry_points", {})
                                                       .items()
                for grobj in [EntryPointGroup.from_name(group)]
                for e in eps
            ],
            dependency_rels = [
                DependencyRelation(
                    project=Project.from_name(p),
                    source_project_id=project.id,
                )
                for p in raw_data["derived"]["dependencies"]
            ],
            valid = raw_data["valid"],
            keywords = [
                Keyword(name=k) for k in raw_data["derived"]["keywords"]
            ],
            files = [File(path=f) for f in file_paths],
            modules = [Module(name=m) for m in raw_data["derived"]["modules"]],
        )


S.Index('wheel_data_processed_idx', WheelData.processed.desc())


class EntryPointGroup(Base):
    """ An entry point group """

    __tablename__ = 'entry_point_groups'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    name        = S.Column(S.Unicode(2048), nullable=False, unique=True)
    #: A brief Markdown description of the group for display in the web
    #: interface
    summary     = S.Column(S.Unicode(2048), nullable=True, default=None)
    #: A longer Markdown description of the group for display in the web
    #: interface
    description = S.Column(S.Unicode(65535), nullable=True, default=None)

    def __repr__(self):
        return reprify(self, ['name'])

    @classmethod
    def from_name(cls, name: str):
        """
        Construct an `EntryPointGroup` with the given name and return it.  If
        such a group already exists, return that one instead.
        """
        epg = cls.query.filter(cls.name == name).one_or_none()
        if epg is None:
            epg = cls(name=name)
            db.session.add(epg)
        return epg


class EntryPoint(Base):
    """ An entry point registered by a wheel """

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
    """ A file in a wheel """

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
    path = S.Column(S.Unicode(2048), nullable=False)


class Module(Base):
    """ A Python module in a wheel """

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
    """ A keyword declared by a wheel """

    __tablename__ = 'keywords'
    __table_args__ = (S.UniqueConstraint('wheel_data_id', 'name'),)

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


class OrphanWheel(Base):
    """
    If the XML-RPC changelog reports the uploading of a wheel that can't be
    found in the JSON API, we blame caching and add the wheel to this "orphan
    wheel" table for periodic re-checking until either it's found or it's been
    so long that we give up.

    (It's also possible that the wheel is missing because the file, release, or
    project has been deleted from PyPI and we haven't gotten to that changelog
    entry yet.  If & when we do get to such an entry, `remove_wheel()` will
    delete the orphan wheel, and `remove_version()` and `remove_project()` will
    delete the orphan wheel via cascading.)

    This system assumes that the "display name" for a PyPI project's version is
    the same in both the XML-RPC API and the JSON API and that it remains
    constant for the lifetime of the version.
    """

    __tablename__ = 'orphan_wheels'

    id = S.Column(S.Integer, primary_key=True, nullable=False)  # noqa: B001
    version_id = S.Column(
        S.Integer,
        S.ForeignKey('versions.id', ondelete='CASCADE'),
        nullable=False,
    )
    version  = relationship('Version')  # No backref
    filename = S.Column(S.Unicode(2048), nullable=False, unique=True)
    uploaded = S.Column(S.DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return reprify(self, ['filename'])

    @property
    def project(self):
        """ The `Project` to which the wheel belongs """
        return self.version.project
