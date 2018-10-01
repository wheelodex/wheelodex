import pytest
from   wheelodex.app import create_app
from   wheelodex.db  import Version, Wheel, WheelDatabase

@pytest.fixture(scope='session')
def tmpdb_inited():
    with create_app().app_context():
        yield WheelDatabase()

@pytest.fixture()
def tmpdb(tmpdb_inited):
    with tmpdb_inited:
        # See <https://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#foreign-key-support>:
        tmpdb_inited.session.execute("PRAGMA foreign_keys=ON")
        try:
            yield tmpdb_inited
        finally:
            tmpdb_inited.session.rollback()

def sort_versions(vs):
    return sorted(vs, key=lambda v: (v.project.name, v.name))

FOOBAR_1_WHEEL = {
    "filename": 'FooBar-1.0-py3-none-any.whl',
    "url":      'http://example.com/FooBar-1.0-py3-none-any.whl',
    "size":     65535,
    "md5":      '1234567890abcdef1234567890abcdef',
    "sha256":   '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    "uploaded": '2018-09-26T15:12:54',
}

FOOBAR_1_DATA = {
    "project": "FooBar",
    "version": "1.0",
    "verifies": True,
    "dist_info": {},
    "derived": {
        "dependencies": [],
        "keywords": [],
        "modules": [],
    },
}

FOOBAR_2_WHEEL = {
    "filename": 'FooBar-2.0-py3-none-any.whl',
    "url":      'http://example.com/FooBar-2.0-py3-none-any.whl',
    "size":     69105,
    "md5":      '1234567890abcdef1234567890abcdef',
    "sha256":   '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    "uploaded": '2018-09-26T15:14:33',
}

FOOBAR_2_DATA = {
    "project": "FooBar",
    "version": "2.0",
    "verifies": True,
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
    "uploaded": '2018-09-27T11:29:39',
}

def test_add_wheel(tmpdb):
    assert tmpdb.iterqueue() == []
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert tmpdb.iterqueue() == [whl1]
    v2 = tmpdb.add_version(p, '2.0')
    whl2 = tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    assert tmpdb.iterqueue() in ([whl1, whl2], [whl2, whl1])
    assert v1.wheels == [whl1]
    assert v2.wheels == [whl2]
    assert tmpdb.get_version(p, '1.0').wheels == [whl1]
    assert tmpdb.get_version(p, '2.0').wheels == [whl2]

def test_add_wheel_extant(tmpdb):
    """
    Add two wheels with the same project, version, & filename and assert that
    only the first one exists
    """
    assert tmpdb.iterqueue() == []
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert tmpdb.iterqueue() == [whl1]
    tmpdb.add_wheel(
        version  = v1,
        filename = 'FooBar-1.0-py3-none-any.whl',
        url      = 'http://example.org/FooBar-1.0-py3-none-any.whl',
        size     = 69105,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:14:33',
    )
    whl, = tmpdb.iterqueue()
    assert v1.wheels == [whl1]
    assert whl.url == FOOBAR_1_WHEEL["url"]
    assert whl.size == FOOBAR_1_WHEEL["size"]
    assert whl.md5 == FOOBAR_1_WHEEL["md5"]
    assert whl.sha256 == FOOBAR_1_WHEEL["sha256"]
    assert whl.uploaded == FOOBAR_1_WHEEL["uploaded"]

def test_remove_wheel(tmpdb):
    assert tmpdb.iterqueue() == []
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    assert tmpdb.iterqueue() == [whl1]
    tmpdb.remove_wheel('FooBar-1.0-py3-none-any.whl')
    assert tmpdb.iterqueue() == []

def test_add_project(tmpdb):
    assert tmpdb.get_all_projects() == []
    tmpdb.add_project('FooBar')
    p, = tmpdb.get_all_projects()
    assert p.name == 'foobar'
    assert p.display_name == 'FooBar'
    assert p.versions == []
    assert p.latest_version is None

def test_add_project_extant(tmpdb):
    assert tmpdb.get_all_projects() == []
    tmpdb.add_project('FooBar')
    tmpdb.add_project('FOOBAR')
    p, = tmpdb.get_all_projects()
    assert p.name == 'foobar'
    assert p.display_name == 'FooBar'
    assert p.versions == []
    assert p.latest_version is None

def test_get_project(tmpdb):
    assert tmpdb.get_all_projects() == []
    tmpdb.add_project('FooBar')
    for name in ['FooBar', 'foobar', 'FOOBAR']:
        p = tmpdb.get_project(name)
        assert p is not None
        assert p.name == 'foobar'
        assert p.display_name == 'FooBar'
    assert tmpdb.get_project('barfoo') is None

def test_remove_project(tmpdb):
    assert tmpdb.get_all_projects() == []
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = tmpdb.add_version(p, '2.0')
    tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    q = tmpdb.add_project('quux')
    v3 = tmpdb.add_version(q, '1.5')
    whl3 = tmpdb.add_wheel(version=v3, **QUUX_1_5_WHEEL)
    tmpdb.remove_project('FooBar')
    assert tmpdb.get_all_projects() in ([p,q], [q,p])
    assert tmpdb.session.query(Version).all() == [v3]
    assert tmpdb.get_version('foobar', '1.0') is None
    assert tmpdb.get_version('foobar', '2.0') is None
    assert tmpdb.session.query(Wheel).all() == [whl3]
    assert p.latest_version is None

def test_add_version_str(tmpdb):
    assert tmpdb.get_all_projects() == []
    tmpdb.add_project('FooBar')
    tmpdb.add_version('FooBar', '1.0')
    p, = tmpdb.get_all_projects()
    assert p.name == 'foobar'
    v, = p.versions
    assert v.name == '1'
    assert v.display_name == '1.0'
    assert v.wheels == []
    assert p.latest_version == v

def test_add_version_project(tmpdb):
    assert tmpdb.get_all_projects() == []
    p = tmpdb.add_project('FooBar')
    tmpdb.add_version(p, '1.0')
    q, = tmpdb.get_all_projects()
    assert p == q
    v, = p.versions
    assert v.name == '1'
    assert v.display_name == '1.0'
    assert v.wheels == []
    assert p.latest_version == v

def test_add_version_new_str(tmpdb):
    assert tmpdb.get_all_projects() == []
    tmpdb.add_version('FooBar', '1.0')
    p, = tmpdb.get_all_projects()
    assert p.name == 'foobar'
    v, = p.versions
    assert v.name == '1'
    assert v.display_name == '1.0'
    assert v.wheels == []
    assert p.latest_version == v

def test_add_version_extant(tmpdb):
    assert tmpdb.get_all_projects() == []
    p = tmpdb.add_project('FooBar')
    v = tmpdb.add_version('FooBar', '1.0')
    u = tmpdb.add_version('FooBar', '1.0.0')
    assert v == u
    assert p.versions == [v]
    assert v.name == '1'
    assert v.display_name == '1.0'
    assert v.wheels == []
    assert p.latest_version == v

def test_get_version_str(tmpdb):
    assert tmpdb.get_all_projects() == []
    tmpdb.add_project('FooBar')
    tmpdb.add_version('FooBar', '1.0')
    for project in ['foobar', 'FooBar', 'FOOBAR']:
        for version in ['1', '1.0', '1.0.0']:
            v = tmpdb.get_version(project, version)
            assert v.project.name == 'foobar'
            assert v.name == '1'
            assert v.display_name == '1.0'
            assert v.wheels == []
    assert tmpdb.get_version('foobar', '2.0') is None
    assert tmpdb.get_version('quux', '2.0') is None

def test_get_version_project(tmpdb):
    assert tmpdb.get_all_projects() == []
    p = tmpdb.add_project('FooBar')
    tmpdb.add_version('FooBar', '1.0')
    for version in ['1', '1.0', '1.0.0']:
        v = tmpdb.get_version(p, version)
        assert v.project == p
        assert v.name == '1'
        assert v.display_name == '1.0'
        assert v.wheels == []
    assert tmpdb.get_version(p, '2.0') is None

def test_latest_version(tmpdb):
    assert tmpdb.get_all_projects() == []
    p = tmpdb.add_project('FooBar')
    assert p.latest_version is None
    v1 = tmpdb.add_version(p, '1.0')
    assert p.latest_version == v1
    v2 = tmpdb.add_version(p, '2.0')
    assert p.latest_version == v2
    tmpdb.add_version(p, '2.1.dev1')
    assert p.latest_version == v2
    tmpdb.add_version(p, '1.5')
    assert p.latest_version == v2

def test_remove_version(tmpdb):
    assert tmpdb.get_all_projects() == []
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = tmpdb.add_version(p, '2.0')
    tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    tmpdb.remove_version('FooBar', '2.0')
    assert tmpdb.get_all_projects() == [p]
    assert tmpdb.get_version('foobar', '1.0') is not None
    assert tmpdb.get_version('foobar', '2.0') is None
    assert tmpdb.session.query(Version).all() == [v1]
    assert p.latest_version == v1
    assert tmpdb.session.query(Wheel).all() == [whl1]

def test_purge_old_versions_one_version(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    tmpdb.purge_old_versions()
    assert tmpdb.session.query(Version).all() == [v1]

def test_purge_old_versions_two_versions(tmpdb):
    tmpdb.add_version('foobar', '1.0')
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.purge_old_versions()
    assert tmpdb.session.query(Version).all() == [v2]

def test_purge_old_versions_latest_plus_wheel(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v1, v2]

def test_purge_old_versions_latest_plus_wheel_plus_mid(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_version('foobar', '1.5')
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v1, v2]

def test_purge_old_versions_latest_has_wheel_plus_one(tmpdb):
    tmpdb.add_version('foobar', '1.0')
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    tmpdb.purge_old_versions()
    assert tmpdb.session.query(Version).all() == [v2]

def test_purge_old_versions_latest_has_wheel_plus_wheel(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    tmpdb.purge_old_versions()
    assert tmpdb.session.query(Version).all() == [v2]

def test_purge_old_versions_latest_has_data(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v1]

def test_purge_old_versions_latest_plus_data(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v1, v2]

def test_purge_old_versions_latest_plus_data_plus_mid(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    tmpdb.add_version('foobar', '1.5')
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v1, v2]

def test_purge_old_versions_latest_plus_wheel_plus_data(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    v3 = tmpdb.add_version('foobar', '3.0')
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v1, v2, v3]

def test_purge_old_versions_latest_plus_wheel_plus_data_plus_mid(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    tmpdb.add_version('foobar', '1.5')
    v2 = tmpdb.add_version('foobar', '2.0')
    tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    tmpdb.add_version('foobar', '2.5')
    v3 = tmpdb.add_version('foobar', '3.0')
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v1, v2, v3]

def test_purge_old_versions_latest_has_data_plus_data(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    v2 = tmpdb.add_version('foobar', '2.0')
    whl2 = tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    tmpdb.add_wheel_data(whl2, FOOBAR_2_DATA)
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v2]

def test_purge_old_versions_latest_has_data_plus_data_plus_mid(tmpdb):
    v1 = tmpdb.add_version('foobar', '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    tmpdb.add_version('foobar', '1.5')
    v2 = tmpdb.add_version('foobar', '2.0')
    whl2 = tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    tmpdb.add_wheel_data(whl2, FOOBAR_2_DATA)
    tmpdb.purge_old_versions()
    assert sort_versions(tmpdb.session.query(Version).all()) == [v2]

def test_preferred_wheel_two_data(tmpdb):
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    v2 = tmpdb.add_version(p, '2.0')
    whl2 = tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    tmpdb.add_wheel_data(whl2, FOOBAR_2_DATA)
    assert p.preferred_wheel == whl2

def test_preferred_wheel_two_wheels_nodata(tmpdb):
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = tmpdb.add_version(p, '2.0')
    tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    assert p.preferred_wheel is None

def test_preferred_wheel_lower_data(tmpdb):
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    tmpdb.add_wheel_data(whl1, FOOBAR_1_DATA)
    v2 = tmpdb.add_version(p, '2.0')
    tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    assert p.preferred_wheel == whl1

def test_preferred_wheel_higher_data(tmpdb):
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    tmpdb.add_wheel(version=v1, **FOOBAR_1_WHEEL)
    v2 = tmpdb.add_version(p, '2.0')
    whl2 = tmpdb.add_wheel(version=v2, **FOOBAR_2_WHEEL)
    tmpdb.add_wheel_data(whl2, FOOBAR_2_DATA)
    assert p.preferred_wheel == whl2

### TODO: TO TEST:
# iterqueue()
#  - Wheels with data are omitted from queue
#  - Wheels with errors are omitted from queue
# Adding WheelData with dependencies, entry points, etc.
# `wheel.data = None` deletes the WheelData entry
# Deleting a Wheel deletes its WheelData
# Deleting a WheelData deletes its dependencies and entry points
# Deleting a WheelData doesn't affect its Wheel
# Version.ordering?
# Project.preferred_wheel when the highest version has multiple wheels with data
