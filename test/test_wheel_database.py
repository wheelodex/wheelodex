from   tempfile     import NamedTemporaryFile
import pytest
import sqlalchemy as S
from   wheelodex.db import WheelDatabase

@pytest.fixture(scope='session')
def tmpdb_inited():
    # pytest's tmpdir can't be used here because of fixture scope mismatch.
    with NamedTemporaryFile() as tmpfile:
        yield WheelDatabase({
            "drivername": "sqlite",
            "database": tmpfile.name,
        })

@pytest.fixture()
def tmpdb(tmpdb_inited):
    with tmpdb_inited:
        try:
            yield tmpdb_inited
        finally:
            tmpdb_inited.session.rollback()

def test_add_wheel(tmpdb):
    assert tmpdb.iterqueue() == []
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(
        version  = v1,
        filename = 'FooBar-1.0-py3-none-any.whl',
        url      = 'http://example.com/FooBar-1.0-py3-none-any.whl',
        size     = 65535,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:12:54',
        queued   = False,
    )
    assert tmpdb.iterqueue() == []
    v2 = tmpdb.add_version(p, '2.0')
    whl2 = tmpdb.add_wheel(
        version = v2,
        filename = 'FooBar-2.0-py3-none-any.whl',
        url      = 'http://example.com/FooBar-2.0-py3-none-any.whl',
        size     = 69105,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:14:33',
        queued   = True,
    )
    assert tmpdb.iterqueue() == [whl2]
    assert v1.wheels == [whl1]
    assert v2.wheels == [whl2]
    assert tmpdb.get_version(p, '1.0').wheels == [whl1]
    assert tmpdb.get_version(p, '2.0').wheels == [whl2]

def test_add_wheel_extant(tmpdb):
    assert tmpdb.iterqueue() == []
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(
        version  = v1,
        filename = 'FooBar-1.0-py3-none-any.whl',
        url      = 'http://example.com/FooBar-1.0-py3-none-any.whl',
        size     = 65535,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:12:54',
        queued   = False,
    )
    assert tmpdb.iterqueue() == []
    tmpdb.add_wheel(
        version  = v1,
        filename = 'FooBar-1.0-py3-none-any.whl',
        url      = 'http://example.org/FooBar-1.0-py3-none-any.whl',
        size     = 69105,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:14:33',
        queued   = True,
    )
    whl, = tmpdb.iterqueue()
    assert v1.wheels == [whl1]
    assert whl.url == 'http://example.com/FooBar-1.0-py3-none-any.whl'
    assert whl.size == 65535
    assert whl.md5 == '1234567890abcdef1234567890abcdef'
    assert whl.sha256 == '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef'
    assert whl.uploaded == '2018-09-26T15:12:54'
    assert whl.queued is True

def test_remove_wheel(tmpdb):
    assert tmpdb.iterqueue() == []
    p = tmpdb.add_project('FooBar')
    v1 = tmpdb.add_version(p, '1.0')
    whl1 = tmpdb.add_wheel(
        version  = v1,
        filename = 'FooBar-1.0-py3-none-any.whl',
        url      = 'http://example.com/FooBar-1.0-py3-none-any.whl',
        size     = 65535,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:12:54',
        queued   = True,
    )
    assert tmpdb.iterqueue() == [whl1]
    tmpdb.remove_wheel('FooBar-1.0-py3-none-any.whl')
    assert tmpdb.iterqueue() == []
    assert tmpdb.get_version(p, '1.0').wheels == []

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
    whl1 = tmpdb.add_wheel(
        version  = v1,
        filename = 'FooBar-1.0-py3-none-any.whl',
        url      = 'http://example.com/FooBar-1.0-py3-none-any.whl',
        size     = 65535,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:12:54',
        queued   = False,
    )
    v2 = tmpdb.add_version(p, '2.0')
    whl2 = tmpdb.add_wheel(
        version = v2,
        filename = 'FooBar-2.0-py3-none-any.whl',
        url      = 'http://example.com/FooBar-2.0-py3-none-any.whl',
        size     = 69105,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:14:33',
        queued   = True,
    )
    q = tmpdb.add_project('quux')
    tmpdb.remove_project('FooBar')
    assert tmpdb.get_all_projects() in ([p,q], [q,p])
    assert tmpdb.get_version('foobar', '1.0') is None
    assert tmpdb.get_version('foobar', '2.0') is None
    assert p.versions == []
    #assert tmpdb.get_project('foobar').versions == []
    assert p.latest_version is None
    assert tmpdb.iterqueue() == []
    assert not S.inspect(p).was_deleted
    assert S.inspect(v1).was_deleted
    assert S.inspect(v2).was_deleted
    assert S.inspect(whl1).was_deleted
    assert S.inspect(whl2).was_deleted
    assert not S.inspect(q).was_deleted

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
    whl1 = tmpdb.add_wheel(
        version  = v1,
        filename = 'FooBar-1.0-py3-none-any.whl',
        url      = 'http://example.com/FooBar-1.0-py3-none-any.whl',
        size     = 65535,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:12:54',
        queued   = True,
    )
    v2 = tmpdb.add_version(p, '2.0')
    whl2 = tmpdb.add_wheel(
        version = v2,
        filename = 'FooBar-2.0-py3-none-any.whl',
        url      = 'http://example.com/FooBar-2.0-py3-none-any.whl',
        size     = 69105,
        md5      = '1234567890abcdef1234567890abcdef',
        sha256   = '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
        uploaded = '2018-09-26T15:14:33',
        queued   = True,
    )
    tmpdb.remove_version('FooBar', '2.0')
    assert tmpdb.get_all_projects() == [p]
    assert tmpdb.get_version('foobar', '1.0') is not None
    assert tmpdb.get_version('foobar', '2.0') is None
    assert p.versions == [v1]
    #assert tmpdb.get_project('foobar').versions == [v1]
    assert p.latest_version == v1
    assert tmpdb.iterqueue() == [whl1]
    assert not S.inspect(p).was_deleted
    assert not S.inspect(v1).was_deleted
    assert not S.inspect(whl1).was_deleted
    assert S.inspect(v2).was_deleted
    assert S.inspect(whl2).was_deleted
