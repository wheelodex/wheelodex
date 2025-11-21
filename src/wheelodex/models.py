"""Database classes"""

from __future__ import annotations
from collections.abc import Sequence
from datetime import datetime, timezone
from itertools import groupby
from typing import TYPE_CHECKING, Annotated, Any, cast
from flask_sqlalchemy import SQLAlchemy
from packaging.utils import canonicalize_name as normalize
from packaging.utils import canonicalize_version as normversion
import sqlalchemy as sa
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    registry,
    relationship,
)
from wheel_inspect import __version__ as wheel_inspect_version
from . import __version__
from .util import JsonWheel, JsonWheelMeta, JsonWheelPyPI, version_sort_key
from .wheel_sort import wheel_sort_key


# <https://mike.depalatis.net/blog/sqlalchemy-timestamps.html>
class DateTime(sa.TypeDecorator):
    impl = sa.DateTime
    cache_ok = True

    def process_result_value(self, value: Any, _dialect: sa.Dialect) -> Any:
        if isinstance(value, datetime) and value.tzinfo is None:
            # Must have come from SQLite during testing
            return value.replace(tzinfo=timezone.utc)
        else:
            return value


class Base(DeclarativeBase):
    registry = registry(type_annotation_map={datetime: DateTime(timezone=True)})


PKey = Annotated[int, mapped_column(primary_key=True)]
Str2048 = Annotated[str, mapped_column(sa.Unicode(2048))]

db = SQLAlchemy(model_class=Base)

# <https://github.com/pallets-eco/flask-sqlalchemy/issues/1186>
if TYPE_CHECKING:
    Model = Base
else:
    Model = db.Model


class PyPISerial(MappedAsDataclass, Model):
    """
    A table for storing the serial ID of the last PyPI event seen.  There
    should never be more than one row in this table.
    """

    __tablename__ = "pypi_serial"

    id: Mapped[PKey] = mapped_column(init=False)
    serial: Mapped[int]

    @classmethod
    def ensure(cls, default: int) -> PyPISerial:
        """
        If there is a serial ID in the database, return it as a `PyPISerial`
        instance.  Otherwise, store the given ``default`` value as the current
        serial ID, and return it as a `PyPISerial` instance.
        """
        ps = db.session.scalars(db.select(cls)).one_or_none()
        if ps is None:
            ps = cls(serial=default)
            db.session.add(ps)
        return ps

    @classmethod
    def get(cls) -> int | None:
        """Returns the serial ID of the last seen PyPI event"""
        ps = db.session.scalars(db.select(cls)).one_or_none()
        return ps and ps.serial

    @classmethod
    def set(cls, value: int) -> None:
        """
        Advances the serial ID of the last seen PyPI event to ``value``.  If
        ``value`` is less than the currently-stored serial, no change is made.
        """
        ps = db.session.scalars(db.select(cls)).one_or_none()
        if ps is None:
            db.session.add(cls(serial=value))
        else:
            ps.serial = max(ps.serial, value)


class Project(MappedAsDataclass, Model):
    """A PyPI project"""

    __tablename__ = "projects"

    id: Mapped[PKey] = mapped_column(init=False)
    #: The project's normalized name
    name: Mapped[Str2048] = mapped_column(unique=True)
    #: The preferred non-normalized form of the project's name
    display_name: Mapped[Str2048] = mapped_column(unique=True)
    #: A summary of the project taken from its most recently-analyzed wheel.
    #: (The summary is stored here instead of in `WheelData` because storing it
    #: in `WheelData` would mean that listing projects with their summaries
    #: would involve a complicated query that ends up being noticeably too
    #: slow.)
    summary: Mapped[Str2048 | None] = mapped_column(default=None)
    versions: Mapped[list[Version]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        init=False,
    )
    #: Whether this project has any wheels known to the database
    has_wheels: Mapped[bool] = mapped_column(default=False)

    @classmethod
    def ensure(cls, name: str) -> Project:
        """
        Construct a `Project` with the given name and return it.  If such a
        project already exists, return that one instead.
        """
        proj = db.session.scalars(
            db.select(cls).filter_by(name=normalize(name))
        ).one_or_none()
        if proj is None:
            proj = cls(name=normalize(name), display_name=name)
            db.session.add(proj)
        return proj

    @classmethod
    def get_or_none(cls, name: str) -> Project | None:
        """
        Return the `Project` with the given name (*modulo* normalization), or
        `None` if there is no such project
        """
        return db.session.scalars(
            db.select(Project).filter_by(name=normalize(name))
        ).one_or_none()

    @property
    def latest_version(self) -> Version | None:
        """
        The `Version` for this `Project` with the highest ``ordering`` value,
        or `None` if there are no `Version`\\s
        """
        return db.session.scalars(
            db.select(Version)
            .filter_by(project=self)
            .order_by(Version.ordering.desc())
            .limit(1)
        ).first()

    @property
    def preferred_wheel(self) -> Wheel | None:
        """
        The project's "preferred wheel": the highest-ordered wheel with data
        for the highest-ordered version
        """
        return db.session.scalars(
            db.select(Wheel)
            .join(Version)
            .filter(Version.project == self)
            .filter(Wheel.data.has())
            .order_by(Version.ordering.desc())
            .order_by(Wheel.ordering.desc())
            .limit(1)
        ).first()

    @property
    def best_wheel(self) -> Wheel | None:
        """
        The project's preferred wheel, if it exists (i.e., if any of the
        project's wheels have data); otherwise, the highest-ordered wheel for
        the highest-ordered version
        """
        return db.session.scalars(
            db.select(Wheel)
            .join(Version)
            .filter(Version.project == self)
            .outerjoin(WheelData)
            .order_by(WheelData.id.isnot(None).desc())
            .order_by(Version.ordering.desc())
            .order_by(Wheel.ordering.desc())
            .limit(1)
        ).first()

    def versions_wheels_grid(self) -> list[tuple[str, list[tuple[Wheel, bool]]]]:
        """
        Returns a "grid" of all of this project's `Wheel`\\s, arranged by
        `Version`.  The return value is a list of pairs in which the first
        element is a `Version`'s ``display_name`` and the second element is a
        list of ``(Wheel, bool)`` pairs listing the wheels for that version and
        whether they have data.  The versions are ordered from highest
        ``ordering`` to lowest, and the `Wheel`\\s within each version are
        ordered from highest ``ordering`` to lowest.  Versions that do not have
        wheels are ignored.
        """
        q = db.session.execute(
            db.select(Version.display_name, Wheel, WheelData.id.isnot(None))
            .join(Wheel, Version.wheels)
            .outerjoin(WheelData)
            .filter(Version.project == self)
            .order_by(Version.ordering.desc())
            .order_by(Wheel.ordering.desc())
        )
        results = []
        for v, ws in groupby(q, lambda r: r[0]):
            results.append((v, [(w, b) for _, w, b in ws]))
        return results

    def update_has_wheels(self) -> None:
        """Update the value of the `Project`'s ``has_wheels`` attribute"""
        self.has_wheels = db.session.scalar(
            db.exists()
            .where(Version.project_id == self.id)
            .where(Wheel.version_id == Version.id)
            .select()
        )

    def rdepends_query(self) -> sa.Select:
        """
        Returns a query object that returns all `Project`\\s that depend on
        this `Project`, ordered by name.
        """
        subq = (
            db.select(Project.id.distinct().label("id"))
            .join(
                DependencyRelation, Project.id == DependencyRelation.source_project_id
            )
            .where(DependencyRelation.project_id == self.id)
            .subquery()
        )
        return cast(
            sa.Select,
            db.select(Project)
            .join(subq, Project.id == subq.c.id)
            .order_by(Project.name.asc()),
        )

    def rdepends_count(self) -> int:
        """Returns the number of `Project`\\s that depend on this `Project`"""
        r = db.session.scalar(
            db.select(
                db.func.count(DependencyRelation.source_project_id.distinct())
            ).where(DependencyRelation.project_id == self.id)
        )
        assert isinstance(r, int)
        return r

    def remove(self) -> None:
        """
        Delete all `Version`\\s (and `Wheel`\\s etc.) for this `Project`.  The
        `Project` entry itself is retained in case it's still referenced as a
        dependency of other projects.
        """
        db.session.execute(db.delete(Version).where(Version.project == self))
        self.has_wheels = False

    def ensure_version(self, version: str) -> Version:
        """
        Create a `Version` for the `Project` with the given version string and
        return it; the ``ordering`` values for the project's `Version`\\s are
        updated as well.  If there already exists a version with the same
        details, do nothing and return that instead.
        """
        vnorm = normversion(version)
        v = db.session.scalars(
            db.select(Version).filter_by(project=self, name=vnorm)
        ).one_or_none()
        if v is None:
            v = Version(project=self, name=vnorm, display_name=version)
            db.session.add(v)
            for i, u in enumerate(
                ### TODO: Is `self.versions` safe to use when some of its
                ### elements may have been deleted earlier in the transaction?
                sorted(self.versions, key=lambda x: version_sort_key(x.name))
            ):
                u.ordering = i
        return v

    def get_version_or_none(self, version: str) -> Version | None:
        """
        Return the project's `Version` with the given version string (*modulo*
        canonicalization), or `None` if there is no such version
        """
        return db.session.scalars(
            db.select(Version).filter_by(project=self, name=normversion(version))
        ).one_or_none()

    def remove_version(self, version: str) -> None:
        """
        Delete the project's `Version` (and `Wheel`\\s etc.) entries for the
        given version string
        """
        db.session.execute(
            db.delete(Version)
            .where(Version.project == self)
            .where(Version.name == normversion(version))
        )
        self.update_has_wheels()


class Version(MappedAsDataclass, Model):
    """A version (a.k.a. release) of a `Project`"""

    __tablename__ = "versions"
    __table_args__ = (sa.UniqueConstraint("project_id", "name"),)

    id: Mapped[PKey] = mapped_column(init=False)
    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        init=False,
    )
    project: Mapped[Project] = relationship(back_populates="versions")
    #: The normalized version string
    name: Mapped[Str2048]
    #: The preferred non-normalized version string
    display_name: Mapped[Str2048]
    wheels: Mapped[list[Wheel]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        init=False,
    )
    #: The index of this version when all versions for the project are sorted
    #: in PEP 440 order with prereleases at the bottom.  (The latest version
    #: has the highest `ordering` value.)  This column is set every time a new
    #: version is added to the project with `Project.ensure_version()`.
    ordering: Mapped[int] = mapped_column(default=0)

    def ensure_wheel(
        self,
        *,
        filename: str,
        url: str,
        size: int,
        md5: str,
        sha256: str,
        uploaded: datetime,
    ) -> Wheel:
        """
        Registers a wheel for the `Version` and updates the ``ordering`` values
        for the `Version`'s `Wheel`\\s.  The new `Wheel` object is returned.
        If a wheel with the given filename is already registered, no change is
        made to the database, and the already-registered wheel is returned.
        """
        whl = db.session.scalars(
            db.select(Wheel).filter_by(filename=filename)
        ).one_or_none()
        if whl is None:
            whl = Wheel(
                version=self,
                filename=filename,
                url=url,
                size=size,
                md5=md5,
                sha256=sha256,
                uploaded=uploaded,
            )
            db.session.add(whl)
            for i, w in enumerate(
                ### TODO: Is `self.wheels` safe to use when some of its
                ### elements may have been deleted earlier in the transaction?
                sorted(self.wheels, key=lambda x: wheel_sort_key(x.filename))
            ):
                w.ordering = i
            self.project.has_wheels = True
        return whl


class Wheel(MappedAsDataclass, Model):
    """A wheel belonging to a `Version`"""

    __tablename__ = "wheels"

    id: Mapped[PKey] = mapped_column(init=False)
    filename: Mapped[Str2048] = mapped_column(unique=True)
    url: Mapped[Str2048]
    version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("versions.id", ondelete="CASCADE"),
        init=False,
    )
    version: Mapped[Version] = relationship(back_populates="wheels")
    size: Mapped[int]
    md5: Mapped[str] = mapped_column(sa.Unicode(32))
    sha256: Mapped[str] = mapped_column(sa.Unicode(64))
    uploaded: Mapped[datetime]
    errors: Mapped[list[ProcessingError]] = relationship(
        back_populates="wheel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        init=False,
    )
    data: Mapped[WheelData | None] = relationship(
        back_populates="wheel",
        cascade="all, delete-orphan",
        passive_deletes=True,
        default=None,
    )
    #: The index of this wheel when all wheels for the version are sorted by
    #: applying `wheel_sort_key()` to their filenames.  This column is set
    #: every time a new wheel is added to the version with `ensure_wheel()`.
    ordering: Mapped[int] = mapped_column(default=0)

    @property
    def project(self) -> Project:
        """The `Project` to which the wheel belongs"""
        return self.version.project

    def set_data(self, raw_data: dict) -> None:
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

    def add_error(self, errmsg: str) -> None:
        """
        Register an error that occurred while processing this wheel for data
        """
        self.errors.append(
            ProcessingError(
                errmsg=errmsg[-65535:],
                timestamp=datetime.now(timezone.utc),
                wheelodex_version=__version__,
                wheel_inspect_version=wheel_inspect_version,
            )
        )

    def as_json(self) -> dict:
        """
        Returns a JSONable representation (i.e., a `dict` composed entirely of
        primitive types that can be directly serialized to JSON) of the wheel
        and its data, if any
        """
        pypi = JsonWheelPyPI(
            filename=self.filename,
            url=self.url,
            project=self.project.display_name,
            version=self.version.display_name,
            size=self.size,
            md5=self.md5,
            sha256=self.sha256,
            uploaded=self.uploaded,
        )
        if self.data is not None:
            data = self.data.raw_data
            meta = JsonWheelMeta(
                processed=self.data.processed,
                wheel_inspect_version=self.data.wheel_inspect_version,
            )
        else:
            data = None
            meta = None
        r = JsonWheel(
            pypi=pypi, data=data, wheelodex=meta, errored=bool(self.errors)
        ).model_dump(mode="json")
        assert isinstance(r, dict)
        return r

    @classmethod
    def add_from_json(cls, data: dict) -> None:
        """
        Add a wheel (possibly with data) from a structure produced by
        `Wheel.as_json()`
        """
        about = JsonWheel.model_validate(data)
        version = Project.ensure(about.pypi.project).ensure_version(about.pypi.version)
        whl = version.ensure_wheel(
            filename=about.pypi.filename,
            url=about.pypi.url,
            size=about.pypi.size,
            md5=about.pypi.md5,
            sha256=about.pypi.sha256,
            uploaded=about.pypi.uploaded,
        )
        if about.data is not None and whl.data is None:
            whl.set_data(about.data)
            assert whl.data is not None
            assert about.wheelodex is not None  # type: ignore[unreachable]
            whl.data.processed = about.wheelodex.processed
            whl.data.wheel_inspect_version = about.wheelodex.wheel_inspect_version

    @classmethod
    def to_process(cls, max_wheel_size: int | None = None) -> Sequence[Wheel]:
        """
        Returns the "queue" of wheels to process: a list of all wheels with
        neither data nor errors for the latest nonempty (i.e., having wheels)
        version of each project

        :param int max_wheel_size: If set, only wheels this size or smaller are
            returned
        """
        subq = (
            db.select(Project.id, db.func.max(Version.ordering).label("max_order"))
            .join(Version)
            .join(Wheel)
            .group_by(Project.id)
            .subquery()
        )
        q = (
            db.select(Wheel)
            .join(Version)
            .join(Project)
            .join(
                subq, (Project.id == subq.c.id) & (Version.ordering == subq.c.max_order)
            )
            .filter(~Wheel.data.has())
            .filter(~Wheel.errors.any())
        )
        if max_wheel_size is not None:
            q = q.filter(Wheel.size <= max_wheel_size)
        return db.session.scalars(q).all()


class ProcessingError(MappedAsDataclass, Model):
    """An error that occurred while processing a `Wheel` for data"""

    __tablename__ = "processing_errors"

    id: Mapped[PKey] = mapped_column(init=False)
    wheel_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheels.id", ondelete="CASCADE"),
        init=False,
    )
    wheel: Mapped[Wheel] = relationship(back_populates="errors", init=False)
    errmsg: Mapped[str] = mapped_column(sa.Unicode(65535))
    timestamp: Mapped[datetime]
    wheelodex_version: Mapped[str] = mapped_column(sa.Unicode(32))
    wheel_inspect_version: Mapped[str | None] = mapped_column(sa.Unicode(32))


class DependencyRelation(MappedAsDataclass, Model):
    """
    An association object that maps `WheelData` values to the `Project`\\s
    listed in their :mailheader:`Requires-Dist` fields
    """

    __tablename__ = "dependency_tbl"

    wheel_data_id: Mapped[PKey] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"), init=False
    )

    project_id: Mapped[PKey] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="RESTRICT"), init=False
    )
    project: Mapped[Project] = relationship(foreign_keys=[project_id])

    #: A redundant reference to the project to which the wheel belongs, stored
    #: here to make some queries faster:
    source_project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="CASCADE")
    )


class WheelData(MappedAsDataclass, Model):
    """Information about a `Wheel` produced with `inspect_wheel()`"""

    __tablename__ = "wheel_data"

    id: Mapped[PKey] = mapped_column(init=False)
    wheel_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheels.id", ondelete="CASCADE"),
        init=False,
        unique=True,
    )
    wheel: Mapped[Wheel] = relationship(back_populates="data", init=False)
    raw_data: Mapped[Any] = mapped_column(sa.JSON, nullable=False)
    #: The time at which the raw data was extracted from the wheel and added to
    #: the database
    processed: Mapped[datetime]
    #: The version of wheel-inspect that produced the ``raw_data``
    wheel_inspect_version: Mapped[str] = mapped_column(sa.Unicode(32))
    ### TODO: What are the right `cascade` and `passive_deletes` settings for
    ### this relationship?
    dependency_rels: Mapped[list[DependencyRelation]] = relationship()
    valid: Mapped[bool]
    entry_points: Mapped[list[EntryPoint]] = relationship(
        back_populates="wheel_data", cascade="all, delete-orphan", passive_deletes=True
    )
    files: Mapped[list[File]] = relationship(
        back_populates="wheel_data", cascade="all, delete-orphan", passive_deletes=True
    )
    modules: Mapped[list[Module]] = relationship(
        back_populates="wheel_data", cascade="all, delete-orphan", passive_deletes=True
    )
    keywords: Mapped[list[Keyword]] = relationship(
        back_populates="wheel_data", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def dependencies(self) -> list[Project]:
        return [rel.project for rel in self.dependency_rels]

    @classmethod
    def from_raw_data(cls, raw_data: dict) -> WheelData:
        """
        Construct a new `WheelData` object, complete with related objects, from
        the return value of a call to `inspect_wheel()`
        """
        file_paths = {
            # Make this a set because some wheels have duplicate entries in
            # their RECORDs
            f["path"]
            for f in raw_data["dist_info"].get("record", [])
        }
        project = Project.ensure(raw_data["project"])
        return cls(
            raw_data=raw_data,
            processed=datetime.now(timezone.utc),
            wheel_inspect_version=wheel_inspect_version,
            entry_points=[
                EntryPoint(group=grobj, name=e)
                for group, eps in raw_data["dist_info"].get("entry_points", {}).items()
                for grobj in [EntryPointGroup.ensure(group)]
                for e in eps
            ],
            dependency_rels=[
                DependencyRelation(
                    project=Project.ensure(p),
                    source_project_id=project.id,
                )
                for p in raw_data["derived"]["dependencies"]
            ],
            valid=raw_data["valid"],
            keywords=[Keyword(name=k) for k in raw_data["derived"]["keywords"]],
            files=[File(path=f) for f in file_paths],
            modules=[Module(name=m) for m in raw_data["derived"]["modules"]],
        )


sa.Index("wheel_data_processed_idx", WheelData.processed.desc())


class EntryPointGroup(MappedAsDataclass, Model):
    """An entry point group"""

    __tablename__ = "entry_point_groups"

    id: Mapped[PKey] = mapped_column(init=False)
    name: Mapped[Str2048] = mapped_column(unique=True)
    #: A brief Markdown description of the group for display in the web
    #: interface
    summary: Mapped[Str2048 | None] = mapped_column(default=None)
    #: A longer Markdown description of the group for display in the web
    #: interface
    description: Mapped[str | None] = mapped_column(sa.Unicode(65535), default=None)

    @classmethod
    def ensure(cls, name: str) -> EntryPointGroup:
        """
        Construct an `EntryPointGroup` with the given name and return it.  If
        such a group already exists, return that one instead.
        """
        epg = db.session.scalars(db.select(cls).filter_by(name=name)).one_or_none()
        if epg is None:
            epg = cls(name=name)
            db.session.add(epg)
        return epg


class EntryPoint(MappedAsDataclass, Model):
    """An entry point registered by a wheel"""

    __tablename__ = "entry_points"

    id: Mapped[PKey] = mapped_column(init=False)
    wheel_data_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"),
        init=False,
    )
    wheel_data: Mapped[WheelData] = relationship(
        back_populates="entry_points", init=False
    )
    group_id: Mapped[int] = mapped_column(
        sa.ForeignKey("entry_point_groups.id", ondelete="RESTRICT"),
        init=False,
    )
    group: Mapped[EntryPointGroup] = relationship()
    name: Mapped[Str2048]


class File(MappedAsDataclass, Model):
    """A file in a wheel"""

    __tablename__ = "files"
    __table_args__ = (sa.UniqueConstraint("wheel_data_id", "path"),)

    id: Mapped[PKey] = mapped_column(init=False)
    wheel_data_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"),
        init=False,
    )
    wheel_data: Mapped[WheelData] = relationship(back_populates="files", init=False)
    path: Mapped[Str2048]


class Module(MappedAsDataclass, Model):
    """A Python module in a wheel"""

    __tablename__ = "modules"
    __table_args__ = (sa.UniqueConstraint("wheel_data_id", "name"),)

    id: Mapped[PKey] = mapped_column(init=False)
    wheel_data_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"),
        init=False,
    )
    wheel_data: Mapped[WheelData] = relationship(back_populates="modules", init=False)
    name: Mapped[Str2048]


class Keyword(MappedAsDataclass, Model):
    """A keyword declared by a wheel"""

    __tablename__ = "keywords"
    __table_args__ = (sa.UniqueConstraint("wheel_data_id", "name"),)

    id: Mapped[PKey] = mapped_column(init=False)
    wheel_data_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"),
        init=False,
    )
    wheel_data: Mapped[WheelData] = relationship(back_populates="keywords", init=False)
    name: Mapped[Str2048]


class OrphanWheel(MappedAsDataclass, Model):
    """
    If the XML-RPC changelog reports the uploading of a wheel that can't be
    found in the JSON API, we blame caching and add the wheel to this "orphan
    wheel" table for periodic re-checking until either it's found or it's been
    so long that we give up.

    (It's also possible that the wheel is missing because the file, release, or
    project has been deleted from PyPI and we haven't gotten to that changelog
    entry yet.  If & when we do get to such an entry, `remove_wheel()` will
    delete the orphan wheel, and `Project.remove_version()` and
    `Project.remove()` will delete the orphan wheel via cascading.)

    This system assumes that the "display name" for a PyPI project's version is
    the same in both the XML-RPC API and the JSON API and that it remains
    constant for the lifetime of the version.
    """

    __tablename__ = "orphan_wheels"

    id: Mapped[PKey] = mapped_column(init=False)
    version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("versions.id", ondelete="CASCADE"),
        init=False,
    )
    version: Mapped[Version] = relationship()  # No backref
    filename: Mapped[Str2048] = mapped_column(unique=True)
    uploaded: Mapped[datetime]

    @property
    def project(self) -> Project:
        """The `Project` to which the wheel belongs"""
        return self.version.project

    @classmethod
    def register(cls, version: Version, filename: str, uploaded: datetime) -> None:
        """
        Register an `OrphanWheel` for the given version, with the given
        filename, uploaded at ``uploaded``.  If an orphan wheel with the given
        filename has already been registered, update its ``uploaded`` timestamp
        and do nothing else.
        """
        whl = db.session.scalars(
            db.select(OrphanWheel).filter_by(filename=filename)
        ).one_or_none()
        if whl is None:
            whl = OrphanWheel(version=version, filename=filename, uploaded=uploaded)
            db.session.add(whl)
        else:
            # If they keep uploading the wheel, keep checking the JSON API for
            # it.
            whl.uploaded = uploaded
