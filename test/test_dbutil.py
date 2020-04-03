from   datetime         import datetime
import pytest
from   wheelodex.app    import create_app
from   wheelodex.dbutil import (
    add_orphan_wheel,
    add_project, add_version, add_wheel,
    get_project, get_version,
    iterqueue,
    purge_old_versions,
    remove_project, remove_version, remove_wheel,
)
from   wheelodex.models import OrphanWheel, Project, Version, Wheel, db
from   wheelodex.util   import parse_timestamp

@pytest.fixture(scope='session')
def tmpdb_inited():
    with create_app().app_context():
        # See <https://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#foreign-key-support>:
        db.session.execute("PRAGMA foreign_keys=ON")
        db.create_all()
        yield

@pytest.fixture(autouse=True)
def tmpdb(tmpdb_inited):
    try:
        yield
    finally:
        db.session.rollback()

def sort_versions(vs):
    return sorted(vs, key=lambda v: (v.project.name, v.name))

def sort_wheels(ws):
    return sorted(ws, key=lambda w: w.filename)

FOOBAR_1_WHEEL = {
    "filename": 'FooBar-1.0-py3-none-any.whl',
    "url":      'http://example.com/FooBar-1.0-py3-none-any.whl',
    "size":     65535,
    "md5":      '1234567890abcdef1234567890abcdef',
    "sha256":   '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    "uploaded": '2018-09-26T15:12:54.123456Z',
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

FOOBAR_1_WHEEL2 = {
    "filename": 'FooBar-1.0-py2-none-any.whl',
    "url":      'http://example.com/FooBar-1.0-py2-none-any.whl',
    "size":     65500,
    "md5":      '1234567890abcdef1234567890abcdef',
    "sha256":   '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    "uploaded": '2018-10-03T11:27:17.234567Z',
}

FOOBAR_2_WHEEL = {
    "filename": 'FooBar-2.0-py3-none-any.whl',
    "url":      'http://example.com/FooBar-2.0-py3-none-any.whl',
    "size":     69105,
    "md5":      '1234567890abcdef1234567890abcdef',
    "sha256":   '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    "uploaded": '2018-09-26T15:14:33.345678Z',
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

QUUX_1_5_WHEEL = {
    "filename": 'quux-1.5-py3-none-any.whl',
    "url":      'http://example.com/quux-1.5-py3-none-any.whl',
    "size":     2048,
    "md5":      '1234567890abcdef1234567890abcdef',
    "sha256":   '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    "uploaded": '2018-09-27T11:29:39.456789Z',
}

def test_add_wheel():
    assert Wheel.query.all() == []
    p = add_project('FooBar')
    assert not p.has_wheels
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert Wheel.query.all() == [whl1]
    assert p.has_wheels
    v2 = add_version(p, '2.0')
    whl2 = add_wheel(version=v2, **FOOBAR_2_WHEEL)
    assert sort_wheels(Wheel.query.all()) == [whl1, whl2]
    assert v1.wheels == [whl1]
    assert v2.wheels == [whl2]
    assert get_version(p, '1.0').wheels == [whl1]
    assert get_version(p, '2.0').wheels == [whl2]

def test_add_wheel_extant():
    """
    Add two wheels with the same project, version, & filename and assert that
    only the first one exists
    """
    assert Wheel.query.all() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert Wheel.query.all() == [whl1]
    add_wheel(
        version  = v1,
        filename = 'FooBar-1.0-py3-none-any.whl',
        url      = 'http://example.org/FooBar-1.0-py3-none-any.whl',
        size     = 69105,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:14:33.987654Z',
    )
    whl, = Wheel.query.all()
    assert v1.wheels == [whl1]
    assert whl.url == FOOBAR_1_WHEEL["url"]
    assert whl.size == FOOBAR_1_WHEEL["size"]
    assert whl.md5 == FOOBAR_1_WHEEL["md5"]
    assert whl.sha256 == FOOBAR_1_WHEEL["sha256"]
    assert whl.uploaded == parse_timestamp(FOOBAR_1_WHEEL["uploaded"])

def test_remove_wheel():
    assert Wheel.query.all() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert Wheel.query.all() == [whl1]
    remove_wheel('FooBar-1.0-py3-none-any.whl')
    assert Wheel.query.all() == []
    assert not p.has_wheels

def test_add_project():
    assert Project.query.all() == []
    add_project('FooBar')
    p, = Project.query.all()
    assert p.name == 'foobar'
    assert p.display_name == 'FooBar'
    assert p.versions == []
    assert p.latest_version is None

def test_add_project_extant():
    assert Project.query.all() == []
    add_project('FooBar')
    add_project('FOOBAR')
    p, = Project.query.all()
    assert p.name == 'foobar'
    assert p.display_name == 'FooBar'
    assert p.versions == []
    assert p.latest_version is None

def test_get_project():
    assert Project.query.all() == []
    add_project('FooBar')
    for name in ['FooBar', 'foobar', 'FOOBAR']:
        p = get_project(name)
        assert p is not None
        assert p.name == 'foobar'
        assert p.display_name == 'FooBar'
    assert get_project('barfoo') is None

def test_remove_project():
    assert Project.query.all() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = add_version(p, '2.0')
    add_wheel(version=v2, **FOOBAR_2_WHEEL)
    q = add_project('quux')
    v3 = add_version(q, '1.5')
    whl3 = add_wheel(version=v3, **QUUX_1_5_WHEEL)
    remove_project('FooBar')
    assert Project.query.all() in ([p,q], [q,p])
    assert Version.query.all() == [v3]
    assert get_version('foobar', '1.0') is None
    assert get_version('foobar', '2.0') is None
    assert Wheel.query.all() == [whl3]
    assert p.latest_version is None
    assert not p.has_wheels

def test_add_version_str():
    assert Project.query.all() == []
    add_project('FooBar')
    add_version('FooBar', '1.0')
    p, = Project.query.all()
    assert p.name == 'foobar'
    v, = p.versions
    assert v.name == '1'
    assert v.display_name == '1.0'
    assert v.wheels == []
    assert p.latest_version == v

def test_add_version_project():
    assert Project.query.all() == []
    p = add_project('FooBar')
    add_version(p, '1.0')
    q, = Project.query.all()
    assert p == q
    v, = p.versions
    assert v.name == '1'
    assert v.display_name == '1.0'
    assert v.wheels == []
    assert p.latest_version == v

def test_add_version_new_str():
    assert Project.query.all() == []
    add_version('FooBar', '1.0')
    p, = Project.query.all()
    assert p.name == 'foobar'
    v, = p.versions
    assert v.name == '1'
    assert v.display_name == '1.0'
    assert v.wheels == []
    assert p.latest_version == v

def test_add_version_extant():
    assert Project.query.all() == []
    p = add_project('FooBar')
    v = add_version('FooBar', '1.0')
    u = add_version('FooBar', '1.0.0')
    assert v == u
    assert p.versions == [v]
    assert v.name == '1'
    assert v.display_name == '1.0'
    assert v.wheels == []
    assert p.latest_version == v

def test_get_version_str():
    assert Project.query.all() == []
    add_project('FooBar')
    add_version('FooBar', '1.0')
    for project in ['foobar', 'FooBar', 'FOOBAR']:
        for version in ['1', '1.0', '1.0.0']:
            v = get_version(project, version)
            assert v.project.name == 'foobar'
            assert v.name == '1'
            assert v.display_name == '1.0'
            assert v.wheels == []
    assert get_version('foobar', '2.0') is None
    assert get_version('quux', '2.0') is None

def test_get_version_project():
    assert Project.query.all() == []
    p = add_project('FooBar')
    add_version('FooBar', '1.0')
    for version in ['1', '1.0', '1.0.0']:
        v = get_version(p, version)
        assert v.project == p
        assert v.name == '1'
        assert v.display_name == '1.0'
        assert v.wheels == []
    assert get_version(p, '2.0') is None

def test_latest_version():
    assert Project.query.all() == []
    p = add_project('FooBar')
    assert p.latest_version is None
    v1 = add_version(p, '1.0')
    assert p.latest_version == v1
    v2 = add_version(p, '2.0')
    assert p.latest_version == v2
    add_version(p, '2.1.dev1')
    assert p.latest_version == v2
    add_version(p, '1.5')
    assert p.latest_version == v2

def test_remove_version():
    assert Project.query.all() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = add_version(p, '2.0')
    add_wheel(version=v2, **FOOBAR_2_WHEEL)
    remove_version('FooBar', '2.0')
    assert Project.query.all() == [p]
    assert get_version('foobar', '1.0') is not None
    assert get_version('foobar', '2.0') is None
    assert Version.query.all() == [v1]
    assert p.latest_version == v1
    assert Wheel.query.all() == [whl1]
    assert p.has_wheels

def test_purge_old_versions_one_version():
    v1 = add_version('foobar', '1.0')
    purge_old_versions()
    assert Version.query.all() == [v1]

def test_purge_old_versions_two_versions():
    add_version('foobar', '1.0')
    v2 = add_version('foobar', '2.0')
    purge_old_versions()
    assert Version.query.all() == [v2]

def test_purge_old_versions_latest_plus_wheel():
    v1 = add_version('foobar', '1.0')
    add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = add_version('foobar', '2.0')
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v1, v2]

def test_purge_old_versions_latest_plus_wheel_plus_mid():
    v1 = add_version('foobar', '1.0')
    add_wheel(version=v1, **FOOBAR_1_WHEEL)
    add_version('foobar', '1.5')
    v2 = add_version('foobar', '2.0')
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v1, v2]

def test_purge_old_versions_latest_has_wheel_plus_one():
    add_version('foobar', '1.0')
    v2 = add_version('foobar', '2.0')
    add_wheel(version=v2, **FOOBAR_2_WHEEL)
    purge_old_versions()
    assert Version.query.all() == [v2]

def test_purge_old_versions_latest_has_wheel_plus_wheel():
    v1 = add_version('foobar', '1.0')
    add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = add_version('foobar', '2.0')
    add_wheel(version=v2, **FOOBAR_2_WHEEL)
    purge_old_versions()
    assert Version.query.all() == [v2]

def test_purge_old_versions_latest_has_data():
    v1 = add_version('foobar', '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v1]

def test_purge_old_versions_latest_plus_data():
    v1 = add_version('foobar', '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = add_version('foobar', '2.0')
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v1, v2]

def test_purge_old_versions_latest_plus_data_plus_mid():
    v1 = add_version('foobar', '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    add_version('foobar', '1.5')
    v2 = add_version('foobar', '2.0')
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v1, v2]

def test_purge_old_versions_latest_plus_wheel_plus_data():
    v1 = add_version('foobar', '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = add_version('foobar', '2.0')
    add_wheel(version=v2, **FOOBAR_2_WHEEL)
    v3 = add_version('foobar', '3.0')
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v1, v2, v3]

def test_purge_old_versions_latest_plus_wheel_plus_data_plus_mid():
    v1 = add_version('foobar', '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    add_version('foobar', '1.5')
    v2 = add_version('foobar', '2.0')
    add_wheel(version=v2, **FOOBAR_2_WHEEL)
    add_version('foobar', '2.5')
    v3 = add_version('foobar', '3.0')
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v1, v2, v3]

def test_purge_old_versions_latest_has_data_plus_data():
    v1 = add_version('foobar', '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = add_version('foobar', '2.0')
    whl2 = add_wheel(version=v2, **FOOBAR_2_WHEEL)
    whl2.set_data(FOOBAR_2_DATA)
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v2]

def test_purge_old_versions_latest_has_data_plus_data_plus_mid():
    v1 = add_version('foobar', '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    add_version('foobar', '1.5')
    v2 = add_version('foobar', '2.0')
    whl2 = add_wheel(version=v2, **FOOBAR_2_WHEEL)
    whl2.set_data(FOOBAR_2_DATA)
    purge_old_versions()
    assert sort_versions(Version.query.all()) == [v2]

def test_preferred_wheel_two_data():
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = add_version(p, '2.0')
    whl2 = add_wheel(version=v2, **FOOBAR_2_WHEEL)
    whl2.set_data(FOOBAR_2_DATA)
    assert p.preferred_wheel == whl2
    assert p.best_wheel == whl2

def test_preferred_wheel_two_wheels_nodata():
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = add_version(p, '2.0')
    whl2 = add_wheel(version=v2, **FOOBAR_2_WHEEL)
    assert p.preferred_wheel is None
    assert p.best_wheel == whl2

def test_preferred_wheel_lower_data():
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    v2 = add_version(p, '2.0')
    add_wheel(version=v2, **FOOBAR_2_WHEEL)
    assert p.preferred_wheel == whl1
    assert p.best_wheel == whl1

def test_preferred_wheel_higher_data():
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = add_version(p, '2.0')
    whl2 = add_wheel(version=v2, **FOOBAR_2_WHEEL)
    whl2.set_data(FOOBAR_2_DATA)
    assert p.preferred_wheel == whl2
    assert p.best_wheel == whl2

def test_iterqueue_skip_data():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert iterqueue() == [whl1]
    whl1.set_data(FOOBAR_1_DATA)
    assert iterqueue() == []

def test_iterqueue_skip_error():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert iterqueue() == [whl1]
    whl1.add_error('Testing')
    assert iterqueue() == []

def test_iterqueue_skip_non_latest():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert iterqueue() == [whl1]
    v2 = add_version(p, '2.0')
    whl2 = add_wheel(version=v2, **FOOBAR_2_WHEEL)
    assert iterqueue() == [whl2]

def test_iterqueue_ignore_empty_latest():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert iterqueue() == [whl1]
    add_version(p, '2.0')
    assert iterqueue() == [whl1]

def test_iterqueue_skip_large():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1b = add_wheel(version=v1, **FOOBAR_1_WHEEL2)
    if whl1.size < whl1b.size:
        assert iterqueue(max_wheel_size=whl1.size) == [whl1]
    else:
        assert iterqueue(max_wheel_size=whl1b.size) == [whl1b]

def test_iterqueue_multiwheel_version():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1b = add_wheel(version=v1, **FOOBAR_1_WHEEL2)
    assert sort_wheels(iterqueue()) == [whl1b, whl1]

def test_iterqueue_multiwheel_version_some_data():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    whl1b = add_wheel(version=v1, **FOOBAR_1_WHEEL2)
    assert iterqueue() == [whl1b]

def test_iterqueue_multiwheel_version_some_error():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.add_error('Testing')
    whl1b = add_wheel(version=v1, **FOOBAR_1_WHEEL2)
    assert iterqueue() == [whl1b]

def test_iterqueue_multiwheel_version_some_data_other_error():
    assert iterqueue() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    whl1b = add_wheel(version=v1, **FOOBAR_1_WHEEL2)
    whl1b.add_error('Testing')
    assert iterqueue() == []

def test_versions_wheels_grid():
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data(FOOBAR_1_DATA)
    whl1b = add_wheel(version=v1, **FOOBAR_1_WHEEL2)
    v2 = add_version(p, '2.0')
    whl2 = add_wheel(version=v2, **FOOBAR_2_WHEEL)
    assert p.versions_wheels_grid() == [
        ('2.0', [(whl2, False)]),
        ('1.0', [(whl1, True), (whl1b, False)]),
    ]

def test_add_orphan_wheel():
    assert OrphanWheel.query.all() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    add_orphan_wheel(v1, 'FooBar-1.0-py3-none-any.whl', 1537974774)
    orphans = OrphanWheel.query.all()
    assert len(orphans) == 1
    assert orphans[0].version == v1
    assert orphans[0].filename == 'FooBar-1.0-py3-none-any.whl'
    # Timestamps returned from a SQLite database are naïve in CPython but aware
    # in PyPy:
    assert orphans[0].uploaded.replace(tzinfo=None) \
        == datetime(2018, 9, 26, 15, 12, 54)
    assert orphans[0].project == p

def test_add_duplicate_orphan_wheel():
    assert OrphanWheel.query.all() == []
    p = add_project('FooBar')
    v1 = add_version(p, '1.0')
    add_orphan_wheel(v1, 'FooBar-1.0-py3-none-any.whl', 1537974774)
    add_orphan_wheel(v1, 'FooBar-1.0-py3-none-any.whl', 1555868651)
    orphans = OrphanWheel.query.all()
    assert len(orphans) == 1
    assert orphans[0].version == v1
    assert orphans[0].filename == 'FooBar-1.0-py3-none-any.whl'
    # Timestamps returned from a SQLite database are naïve in CPython but aware
    # in PyPy:
    assert orphans[0].uploaded.replace(tzinfo=None) \
        == datetime(2019, 4, 21, 17, 44, 11)
    assert orphans[0].project == p

def test_set_data_with_dependency():
    v1 = add_version('foobar', '1.0')
    whl1 = add_wheel(version=v1, **FOOBAR_1_WHEEL)
    whl1.set_data({
        "project": "FooBar",
        "version": "1.0",
        "valid": True,
        "dist_info": {},
        "derived": {
            "dependencies": ["glarch"],
            "keywords": [],
            "modules": [],
        },
    })
    p = get_project('glarch')
    assert whl1.data.dependencies == [p]

### TODO: TO TEST:
# Adding WheelData with (more) dependencies, entry points, etc.
# `wheel.data = None` deletes the WheelData entry
# Deleting a Wheel deletes its WheelData
# Deleting a WheelData deletes its dependencies and entry points
# Deleting a WheelData doesn't affect its Wheel
# Version.ordering?
# Project.preferred_wheel and Project.best_wheel when the highest version has multiple wheels with data
