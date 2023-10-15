""" Database classes """

from __future__ import annotations
from datetime import datetime, timezone
from itertools import groupby
from typing import TYPE_CHECKING, Any
from flask_sqlalchemy import SQLAlchemy
from packaging.utils import canonicalize_name as normalize
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


class Base(DeclarativeBase):
    registry = registry(type_annotation_map={datetime: sa.DateTime(timezone=True)})


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

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    serial: Mapped[int]


class Project(MappedAsDataclass, Model):
    """A PyPI project"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    #: The project's normalized name
    name: Mapped[str] = mapped_column(sa.Unicode(2048), unique=True)
    #: The preferred non-normalized form of the project's name
    display_name: Mapped[str] = mapped_column(sa.Unicode(2048), unique=True)
    #: A summary of the project taken from its most recently-analyzed wheel.
    #: (The summary is stored here instead of in `WheelData` because storing it
    #: in `WheelData` would mean that listing projects with their summaries
    #: would involve a complicated query that ends up being noticeably too
    #: slow.)
    summary: Mapped[str | None] = mapped_column(sa.Unicode(2048), default=None)
    versions: Mapped[list[Version]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        init=False,
    )
    #: Whether this project has any wheels known to the database
    has_wheels: Mapped[bool] = mapped_column(default=False)

    @classmethod
    def from_name(cls, name: str) -> Project:
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


class Version(MappedAsDataclass, Model):
    """A version (a.k.a. release) of a `Project`"""

    __tablename__ = "versions"
    __table_args__ = (sa.UniqueConstraint("project_id", "name"),)

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        init=False,
    )
    project: Mapped[Project] = relationship(back_populates="versions")
    #: The normalized version string
    name: Mapped[str] = mapped_column(sa.Unicode(2048))
    #: The preferred non-normalized version string
    display_name: Mapped[str] = mapped_column(sa.Unicode(2048))
    wheels: Mapped[list[Wheel]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        init=False,
    )
    #: The index of this version when all versions for the project are sorted
    #: in PEP 440 order with prereleases at the bottom.  (The latest version
    #: has the highest `ordering` value.)  This column is set every time a new
    #: version is added to the project with `add_version()`.
    ordering: Mapped[int] = mapped_column(default=0)


class Wheel(MappedAsDataclass, Model):
    """A wheel belonging to a `Version`"""

    __tablename__ = "wheels"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    filename: Mapped[str] = mapped_column(sa.Unicode(2048), unique=True)
    url: Mapped[str] = mapped_column(sa.Unicode(2048))
    version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("versions.id", ondelete="CASCADE"),
        init=False,
    )
    version: Mapped[Version] = relationship(back_populates="wheels")
    size: Mapped[int]
    md5: Mapped[str | None] = mapped_column(sa.Unicode(32))
    sha256: Mapped[str | None] = mapped_column(sa.Unicode(64))
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
    #: every time a new wheel is added to the version with `add_wheel()`.
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

    def as_json(self) -> dict[str, Any]:
        """
        Returns a JSONable representation (i.e., a `dict` composed entirely of
        primitive types that can be directly serialized to JSON) of the wheel
        and its data, if any
        """
        about: dict[str, Any] = {
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


class ProcessingError(MappedAsDataclass, Model):
    """An error that occurred while processing a `Wheel` for data"""

    __tablename__ = "processing_errors"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
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

    wheel_data_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"),
        init=False,
        primary_key=True,
    )

    project_id: Mapped[int] = mapped_column(
        sa.ForeignKey("projects.id", ondelete="RESTRICT"),
        init=False,
        primary_key=True,
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

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
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
        project = Project.from_name(raw_data["project"])
        return cls(
            raw_data=raw_data,
            processed=datetime.now(timezone.utc),
            wheel_inspect_version=wheel_inspect_version,
            entry_points=[
                EntryPoint(group=grobj, name=e)
                for group, eps in raw_data["dist_info"].get("entry_points", {}).items()
                for grobj in [EntryPointGroup.from_name(group)]
                for e in eps
            ],
            dependency_rels=[
                DependencyRelation(
                    project=Project.from_name(p),
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

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str] = mapped_column(sa.Unicode(2048), unique=True)
    #: A brief Markdown description of the group for display in the web
    #: interface
    summary: Mapped[str | None] = mapped_column(sa.Unicode(2048), default=None)
    #: A longer Markdown description of the group for display in the web
    #: interface
    description: Mapped[str | None] = mapped_column(sa.Unicode(65535), default=None)

    @classmethod
    def from_name(cls, name: str) -> EntryPointGroup:
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

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
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
    name: Mapped[str] = mapped_column(sa.Unicode(2048))


class File(MappedAsDataclass, Model):
    """A file in a wheel"""

    __tablename__ = "files"
    __table_args__ = (sa.UniqueConstraint("wheel_data_id", "path"),)

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    wheel_data_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"),
        init=False,
    )
    wheel_data: Mapped[WheelData] = relationship(back_populates="files", init=False)
    path: Mapped[str] = mapped_column(sa.Unicode(2048))


class Module(MappedAsDataclass, Model):
    """A Python module in a wheel"""

    __tablename__ = "modules"
    __table_args__ = (sa.UniqueConstraint("wheel_data_id", "name"),)

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    wheel_data_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"),
        init=False,
    )
    wheel_data: Mapped[WheelData] = relationship(back_populates="modules", init=False)
    name: Mapped[str] = mapped_column(sa.Unicode(2048))


class Keyword(MappedAsDataclass, Model):
    """A keyword declared by a wheel"""

    __tablename__ = "keywords"
    __table_args__ = (sa.UniqueConstraint("wheel_data_id", "name"),)

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    wheel_data_id: Mapped[int] = mapped_column(
        sa.ForeignKey("wheel_data.id", ondelete="CASCADE"),
        init=False,
    )
    wheel_data: Mapped[WheelData] = relationship(back_populates="keywords", init=False)
    name: Mapped[str] = mapped_column(sa.Unicode(2048))


class OrphanWheel(MappedAsDataclass, Model):
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

    __tablename__ = "orphan_wheels"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        sa.ForeignKey("versions.id", ondelete="CASCADE"),
        init=False,
    )
    version: Mapped[Version] = relationship()  # No backref
    filename: Mapped[str] = mapped_column(sa.Unicode(2048), unique=True)
    uploaded: Mapped[datetime]

    @property
    def project(self) -> Project:
        """The `Project` to which the wheel belongs"""
        return self.version.project
