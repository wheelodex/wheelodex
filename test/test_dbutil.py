from __future__ import annotations
from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime, timezone
from typing import TypedDict, TypeVar
import pytest
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from wheelodex.app import create_app
from wheelodex.dbutil import purge_old_versions, remove_wheel
from wheelodex.models import OrphanWheel, Project, Version, Wheel, db

T = TypeVar("T", bound=DeclarativeBase)


@pytest.fixture(scope="session")
def tmpdb_inited() -> Iterator[None]:
    with create_app().app_context():
        # See <https://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#foreign-key-support>:
        db.session.execute(text("PRAGMA foreign_keys=ON"))
        db.create_all()
        yield


@pytest.fixture(autouse=True)
def tmpdb(tmpdb_inited: None) -> Iterator[None]:  # noqa: U100
    try:
        yield
    finally:
        db.session.rollback()


def sort_versions(vs: Iterable[Version]) -> list[Version]:
    return sorted(vs, key=lambda v: (v.project.name, v.name))


def sort_wheels(ws: Iterable[Wheel]) -> list[Wheel]:
    return sorted(ws, key=lambda w: w.filename)


def get_all(cls: type[T]) -> Sequence[T]:
    return db.session.scalars(db.select(cls)).all()


def unixts(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, timezone.utc)


class WheelArgs(TypedDict):
    filename: str
    url: str
    size: int
    md5: str
    sha256: str
    uploaded: datetime


FOOBAR_1_WHEEL: WheelArgs = {
    "filename": "FooBar-1.0-py3-none-any.whl",
    "url": "http://example.com/FooBar-1.0-py3-none-any.whl",
    "size": 65535,
    "md5": "1234567890abcdef1234567890abcdef",
    "sha256": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    "uploaded": datetime.fromisoformat("2018-09-26T15:12:54.123456+00:00"),
}

FOOBAR_1_DATA = {
    "project": "FooBar",
    "version": "1.0",
    "valid": True,
    "dist_info": {},
    "derived": {
        "dependencies": [],
        "keywords": [],
        "modules": [],
    },
}

FOOBAR_1_WHEEL2: WheelArgs = {
    "filename": "FooBar-1.0-py2-none-any.whl",
    "url": "http://example.com/FooBar-1.0-py2-none-any.whl",
    "size": 65500,
    "md5": "1234567890abcdef1234567890abcdef",
    "sha256": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    "uploaded": datetime.fromisoformat("2018-10-03T11:27:17.234567+00:00"),
}

FOOBAR_2_WHEEL: WheelArgs = {
    "filename": "FooBar-2.0-py3-none-any.whl",
    "url": "http://example.com/FooBar-2.0-py3-none-any.whl",
    "size": 69105,
    "md5": "1234567890abcdef1234567890abcdef",
    "sha256": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    "uploaded": datetime.fromisoformat("2018-09-26T15:14:33.345678+00:00"),
}

FOOBAR_2_DATA = {
    "project": "FooBar",
    "version": "2.0",
    "valid": True,
    "dist_info": {},
    "derived": {
        "dependencies": [],
        "keywords": [],
        "modules": [],
    },
}

QUUX_1_5_WHEEL: WheelArgs = {
    "filename": "quux-1.5-py3-none-any.whl",
    "url": "http://example.com/quux-1.5-py3-none-any.whl",
    "size": 2048,
    "md5": "1234567890abcdef1234567890abcdef",
    "sha256": "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    "uploaded": datetime.fromisoformat("2018-09-27T11:29:39.456789+00:00"),
}


def test_ensure_wheel() -> None:
    assert get_all(Wheel) == []
    p = Project.ensure("FooBar")
    assert not p.has_wheels
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    assert get_all(Wheel) == [whl1]
    assert p.has_wheels
    v2 = p.ensure_version("2.0")  # type: ignore[unreachable]
    whl2 = v2.ensure_wheel(**FOOBAR_2_WHEEL)
    assert sort_wheels(get_all(Wheel)) == [whl1, whl2]
    assert v1.wheels == [whl1]
    assert v2.wheels == [whl2]
    assert p.get_version_or_none("1.0").wheels == [whl1]
    assert p.get_version_or_none("2.0").wheels == [whl2]


def test_ensure_wheel_extant() -> None:
    """
    Add two wheels with the same project, version, & filename and assert that
    only the first one exists
    """
    assert get_all(Wheel) == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    assert get_all(Wheel) == [whl1]
    v1.ensure_wheel(
        filename="FooBar-1.0-py3-none-any.whl",
        url="http://example.org/FooBar-1.0-py3-none-any.whl",
        size=69105,
        md5="1234567890abcdef1234567890abcdef",
        sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        uploaded=datetime.fromisoformat("2018-09-26T15:14:33.987654+00:00"),
    )
    (whl,) = get_all(Wheel)
    assert v1.wheels == [whl1]
    assert whl.url == FOOBAR_1_WHEEL["url"]
    assert whl.size == FOOBAR_1_WHEEL["size"]
    assert whl.md5 == FOOBAR_1_WHEEL["md5"]
    assert whl.sha256 == FOOBAR_1_WHEEL["sha256"]
    assert whl.uploaded == FOOBAR_1_WHEEL["uploaded"]


def test_remove_wheel() -> None:
    assert get_all(Wheel) == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    assert get_all(Wheel) == [whl1]
    remove_wheel("FooBar-1.0-py3-none-any.whl")
    assert get_all(Wheel) == []
    assert not p.has_wheels


def test_project_ensure() -> None:
    assert get_all(Project) == []
    Project.ensure("FooBar")
    (p,) = get_all(Project)
    assert p.name == "foobar"
    assert p.display_name == "FooBar"
    assert p.versions == []
    assert p.latest_version is None


def test_project_ensure_extant() -> None:
    assert get_all(Project) == []
    Project.ensure("FooBar")
    Project.ensure("FOOBAR")
    (p,) = get_all(Project)
    assert p.name == "foobar"
    assert p.display_name == "FooBar"
    assert p.versions == []
    assert p.latest_version is None


def test_project_get_or_none() -> None:
    assert get_all(Project) == []
    Project.ensure("FooBar")
    for name in ["FooBar", "foobar", "FOOBAR"]:
        p = Project.get_or_none(name)
        assert p is not None
        assert p.name == "foobar"
        assert p.display_name == "FooBar"
    assert Project.get_or_none("barfoo") is None


def test_project_remove() -> None:
    assert get_all(Project) == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    v1.ensure_wheel(**FOOBAR_1_WHEEL)
    v2 = p.ensure_version("2.0")
    v2.ensure_wheel(**FOOBAR_2_WHEEL)
    q = Project.ensure("quux")
    v3 = q.ensure_version("1.5")
    whl3 = v3.ensure_wheel(**QUUX_1_5_WHEEL)
    p.remove()
    assert get_all(Project) in ([p, q], [q, p])
    assert get_all(Version) == [v3]
    assert p.get_version_or_none("1.0") is None
    assert p.get_version_or_none("2.0") is None
    assert get_all(Wheel) == [whl3]
    assert p.latest_version is None
    assert not p.has_wheels


def test_ensure_version() -> None:
    assert get_all(Project) == []
    p = Project.ensure("FooBar")
    p.ensure_version("1.0")
    (q,) = get_all(Project)
    assert p == q
    (v,) = p.versions
    assert v.name == "1"
    assert v.display_name == "1.0"
    assert v.wheels == []
    assert p.latest_version == v


def test_ensure_version_extant() -> None:
    assert get_all(Project) == []
    p = Project.ensure("FooBar")
    v = p.ensure_version("1.0")
    u = p.ensure_version("1.0.0")
    assert v == u
    assert p.versions == [v]
    assert v.name == "1"
    assert v.display_name == "1.0"
    assert v.wheels == []
    assert p.latest_version == v


def test_get_version_or_none() -> None:
    assert get_all(Project) == []
    p = Project.ensure("FooBar")
    p.ensure_version("1.0")
    for version in ["1", "1.0", "1.0.0"]:
        v = p.get_version_or_none(version)
        assert v is not None
        assert v.project == p
        assert v.name == "1"
        assert v.display_name == "1.0"
        assert v.wheels == []
    assert p.get_version_or_none("2.0") is None


def test_latest_version() -> None:
    assert get_all(Project) == []
    p = Project.ensure("FooBar")
    assert p.latest_version is None
    v1 = p.ensure_version("1.0")
    assert p.latest_version == v1
    v2 = p.ensure_version("2.0")
    assert p.latest_version == v2
    p.ensure_version("2.1.dev1")
    assert p.latest_version == v2
    p.ensure_version("1.5")
    assert p.latest_version == v2


def test_remove_version() -> None:
    assert get_all(Project) == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    v2 = p.ensure_version("2.0")
    v2.ensure_wheel(**FOOBAR_2_WHEEL)
    p.remove_version("2.0")
    assert get_all(Project) == [p]
    assert p.get_version_or_none("1.0") is not None
    assert p.get_version_or_none("2.0") is None
    assert get_all(Version) == [v1]
    assert p.latest_version == v1
    assert get_all(Wheel) == [whl1]
    assert p.has_wheels


def test_purge_old_versions_one_version() -> None:
    v1 = Project.ensure("foobar").ensure_version("1.0")
    purge_old_versions()
    assert get_all(Version) == [v1]


def test_purge_old_versions_two_versions() -> None:
    p = Project.ensure("foobar")
    p.ensure_version("1.0")
    p.ensure_version("2.0")
    purge_old_versions()
    assert get_all(Version) == []


def test_purge_old_versions_latest_plus_wheel() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    v1.ensure_wheel(**FOOBAR_1_WHEEL)
    p.ensure_version("2.0")
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v1]


def test_purge_old_versions_latest_plus_wheel_plus_mid() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    v1.ensure_wheel(**FOOBAR_1_WHEEL)
    p.ensure_version("1.5")
    p.ensure_version("2.0")
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v1]


def test_purge_old_versions_latest_has_wheel_plus_one() -> None:
    p = Project.ensure("foobar")
    p.ensure_version("1.0")
    v2 = p.ensure_version("2.0")
    v2.ensure_wheel(**FOOBAR_2_WHEEL)
    purge_old_versions()
    assert get_all(Version) == [v2]


def test_purge_old_versions_latest_has_wheel_plus_wheel() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    v1.ensure_wheel(**FOOBAR_1_WHEEL)
    v2 = p.ensure_version("2.0")
    v2.ensure_wheel(**FOOBAR_2_WHEEL)
    purge_old_versions()
    assert get_all(Version) == [v2]


def test_purge_old_versions_latest_has_data() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v1]


def test_purge_old_versions_latest_plus_data() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    p.ensure_version("2.0")
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v1]


def test_purge_old_versions_latest_plus_data_plus_mid() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    p.ensure_version("1.5")
    p.ensure_version("2.0")
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v1]


def test_purge_old_versions_latest_plus_wheel_plus_data() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = p.ensure_version("2.0")
    v2.ensure_wheel(**FOOBAR_2_WHEEL)
    p.ensure_version("3.0")
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v1, v2]


def test_purge_old_versions_latest_plus_wheel_plus_data_plus_mid() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    p.ensure_version("1.5")
    v2 = p.ensure_version("2.0")
    v2.ensure_wheel(**FOOBAR_2_WHEEL)
    p.ensure_version("2.5")
    p.ensure_version("3.0")
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v1, v2]


def test_purge_old_versions_latest_has_data_plus_data() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = p.ensure_version("2.0")
    whl2 = v2.ensure_wheel(**FOOBAR_2_WHEEL)
    whl2.set_data(FOOBAR_2_DATA)
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v2]


def test_purge_old_versions_latest_has_data_plus_data_plus_mid() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    p.ensure_version("1.5")
    v2 = p.ensure_version("2.0")
    whl2 = v2.ensure_wheel(**FOOBAR_2_WHEEL)
    whl2.set_data(FOOBAR_2_DATA)
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v2]


def test_purge_old_versions_latest_has_orphans_only_next_has_wheels() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    v1.ensure_wheel(**FOOBAR_1_WHEEL)
    v2 = p.ensure_version("2.0")
    OrphanWheel.register(v2, "FooBar-2.0-py3-none-any.whl", unixts(1537974774))
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v1, v2]


def test_purge_old_versions_latest_has_wheels_next_has_orphans() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    OrphanWheel.register(v1, "FooBar-1.0-py3-none-any.whl", unixts(1537974774))
    v2 = p.ensure_version("2.0")
    v2.ensure_wheel(**FOOBAR_2_WHEEL)
    purge_old_versions()
    assert sort_versions(get_all(Version)) == [v2]


def test_preferred_wheel_two_data() -> None:
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = p.ensure_version("2.0")
    whl2 = v2.ensure_wheel(**FOOBAR_2_WHEEL)
    whl2.set_data(FOOBAR_2_DATA)
    assert p.preferred_wheel == whl2
    assert p.best_wheel == whl2


def test_preferred_wheel_two_wheels_nodata() -> None:
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    v1.ensure_wheel(**FOOBAR_1_WHEEL)
    v2 = p.ensure_version("2.0")
    whl2 = v2.ensure_wheel(**FOOBAR_2_WHEEL)
    assert p.preferred_wheel is None
    assert p.best_wheel == whl2


def test_preferred_wheel_lower_data() -> None:
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = p.ensure_version("2.0")
    v2.ensure_wheel(**FOOBAR_2_WHEEL)
    assert p.preferred_wheel == whl1
    assert p.best_wheel == whl1


def test_preferred_wheel_higher_data() -> None:
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    v1.ensure_wheel(**FOOBAR_1_WHEEL)
    v2 = p.ensure_version("2.0")
    whl2 = v2.ensure_wheel(**FOOBAR_2_WHEEL)
    whl2.set_data(FOOBAR_2_DATA)
    assert p.preferred_wheel == whl2
    assert p.best_wheel == whl2


def test_to_process_skip_data() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    assert Wheel.to_process() == [whl1]
    whl1.set_data(FOOBAR_1_DATA)
    assert Wheel.to_process() == []


def test_to_process_skip_error() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    assert Wheel.to_process() == [whl1]
    whl1.add_error("Testing")
    assert Wheel.to_process() == []


def test_to_process_skip_non_latest() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    assert Wheel.to_process() == [whl1]
    v2 = p.ensure_version("2.0")
    whl2 = v2.ensure_wheel(**FOOBAR_2_WHEEL)
    assert Wheel.to_process() == [whl2]


def test_to_process_ignore_empty_latest() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    assert Wheel.to_process() == [whl1]
    p.ensure_version("2.0")
    assert Wheel.to_process() == [whl1]


def test_to_process_skip_large() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1b = v1.ensure_wheel(**FOOBAR_1_WHEEL2)
    if whl1.size < whl1b.size:
        assert Wheel.to_process(max_wheel_size=whl1.size) == [whl1]
    else:
        assert Wheel.to_process(max_wheel_size=whl1b.size) == [whl1b]


def test_to_process_multiwheel_version() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1b = v1.ensure_wheel(**FOOBAR_1_WHEEL2)
    assert sort_wheels(Wheel.to_process()) == [whl1b, whl1]


def test_to_process_multiwheel_version_some_data() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    whl1b = v1.ensure_wheel(**FOOBAR_1_WHEEL2)
    assert Wheel.to_process() == [whl1b]


def test_to_process_multiwheel_version_some_error() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.add_error("Testing")
    whl1b = v1.ensure_wheel(**FOOBAR_1_WHEEL2)
    assert Wheel.to_process() == [whl1b]


def test_to_process_multiwheel_version_some_data_other_error() -> None:
    assert Wheel.to_process() == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    whl1b = v1.ensure_wheel(**FOOBAR_1_WHEEL2)
    whl1b.add_error("Testing")
    assert Wheel.to_process() == []


def test_versions_wheels_grid() -> None:
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    whl1b = v1.ensure_wheel(**FOOBAR_1_WHEEL2)
    v2 = p.ensure_version("2.0")
    whl2 = v2.ensure_wheel(**FOOBAR_2_WHEEL)
    assert p.versions_wheels_grid() == [
        ("2.0", [(whl2, False)]),
        ("1.0", [(whl1, True), (whl1b, False)]),
    ]


def test_orphan_wheel_register() -> None:
    assert get_all(OrphanWheel) == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    OrphanWheel.register(v1, "FooBar-1.0-py3-none-any.whl", unixts(1537974774))
    orphans = get_all(OrphanWheel)
    assert len(orphans) == 1
    assert orphans[0].version == v1
    assert orphans[0].filename == "FooBar-1.0-py3-none-any.whl"
    assert orphans[0].uploaded == datetime(2018, 9, 26, 15, 12, 54, tzinfo=timezone.utc)
    assert orphans[0].project == p


def test_orphan_wheel_register_duplicate() -> None:
    assert get_all(OrphanWheel) == []
    p = Project.ensure("FooBar")
    v1 = p.ensure_version("1.0")
    OrphanWheel.register(v1, "FooBar-1.0-py3-none-any.whl", unixts(1537974774))
    OrphanWheel.register(v1, "FooBar-1.0-py3-none-any.whl", unixts(1555868651))
    orphans = get_all(OrphanWheel)
    assert len(orphans) == 1
    assert orphans[0].version == v1
    assert orphans[0].filename == "FooBar-1.0-py3-none-any.whl"
    assert orphans[0].uploaded == datetime(2019, 4, 21, 17, 44, 11, tzinfo=timezone.utc)
    assert orphans[0].project == p


def test_set_data_with_dependency() -> None:
    p = Project.ensure("foobar")
    v1 = p.ensure_version("1.0")
    whl1 = v1.ensure_wheel(**FOOBAR_1_WHEEL)
    whl1.set_data(
        {
            "project": "FooBar",
            "version": "1.0",
            "valid": True,
            "dist_info": {},
            "derived": {
                "dependencies": ["glarch"],
                "keywords": [],
                "modules": [],
            },
        }
    )
    p2 = Project.get_or_none("glarch")
    assert whl1.data is not None
    assert whl1.data.dependencies == [p2]


### TODO: TO TEST:
# Adding WheelData with (more) dependencies, entry points, etc.
# `wheel.data = None` deletes the WheelData entry
# Deleting a Wheel deletes its WheelData
# Deleting a WheelData deletes its dependencies and entry points
# Deleting a WheelData doesn't affect its Wheel
# Version.ordering?
# Project.preferred_wheel and Project.best_wheel when the highest version has multiple wheels with data
