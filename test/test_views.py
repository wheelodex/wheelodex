import json
from   pathlib          import Path
from   flask            import current_app
import pytest
from   wheelodex.app    import create_app
from   wheelodex.dbutil import add_wheel_from_json
from   wheelodex.models import db

@pytest.fixture(scope='session')
def sampledb():
    with create_app(TESTING=True).app_context():
        # See <https://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#foreign-key-support>:
        db.session.execute("PRAGMA foreign_keys=ON")
        db.create_all()
        with open(str(Path(__file__).with_name('data') / 'sampledb01.json')) \
                as fp:
            for line in fp:
                add_wheel_from_json(json.loads(line))
        db.session.commit()
        yield

@pytest.fixture()
def client(sampledb):
    return current_app.test_client()

def test_index_200(client):
    rv = client.get('/')
    assert rv.status_code == 200

def test_about_200(client):
    rv = client.get('/about/')
    assert rv.status_code == 200

def test_json_api_200(client):
    rv = client.get('/json-api/')
    assert rv.status_code == 200

def test_recent_wheels_200(client):
    rv = client.get('/recent/')
    assert rv.status_code == 200

def test_rdepends_leaders_200(client):
    rv = client.get('/rdepends-leaders/')
    assert rv.status_code == 200

def test_project_list_200(client):
    rv = client.get('/projects/')
    assert rv.status_code == 200
    assert 'wheel-inspect' in rv.get_data(True)

def test_project_200(client):
    rv = client.get('/projects/wheel-inspect/')
    assert rv.status_code == 200

def test_wheel_data_200(client):
    rv = client.get(
        '/projects/wheel-inspect/wheels/wheel_inspect-1.0.0-py3-none-any.whl/'
    )
    assert rv.status_code == 200

def test_rdepends_200(client):
    rv = client.get('/projects/wheel-inspect/rdepends/')
    assert rv.status_code == 200

def test_entry_point_groups_200(client):
    rv = client.get('/entry-points/')
    assert rv.status_code == 200
    assert 'console_scripts' in rv.get_data(True)

def test_entry_point_groups_sortby_qty_200(client):
    rv = client.get('/entry-points/', query_string={"sortby": "qty"})
    assert rv.status_code == 200
    assert 'console_scripts' in rv.get_data(True)

def test_entry_point_200(client):
    rv = client.get('/entry-points/console_scripts/')
    assert rv.status_code == 200
    data = rv.get_data(True)
    assert 'wheel-inspect' in data
    assert 'wheel2json' in data

def test_search_projects_200(client):
    rv = client.get('/search/projects/', query_string={"q": "wheel-*"})
    assert rv.status_code == 200
    assert 'wheel-inspect' in rv.get_data(True)

@pytest.mark.skip(reason='SQLite does not support array_agg')
def test_search_files_200(client):
    rv = client.get('/search/files/', query_string={"q": "wheel_*"})
    assert rv.status_code == 200
    assert 'wheel_inspect' in rv.get_data(True)

def test_search_modules_200(client):
    rv = client.get('/search/modules/', query_string={"q": "wheel_*"})
    assert rv.status_code == 200
    assert 'wheel_inspect' in rv.get_data(True)

def test_search_commands_200(client):
    rv = client.get('/search/commands/', query_string={"q": "wheel*"})
    assert rv.status_code == 200
    assert 'wheel2json' in rv.get_data(True)

def test_project_json_200(client):
    rv = client.get('/json/projects/wheel-inspect')
    assert rv.status_code == 200
    assert rv.get_json() == {
        "1.0.0": [
            {
                "filename": "wheel_inspect-1.0.0-py3-none-any.whl",
                "has_data": True,
                "href": "/json/wheels/wheel_inspect-1.0.0-py3-none-any.whl.json",
            }
        ]
    }

def test_project_data_json_200(client):
    rv = client.get('/json/projects/wheel-inspect/data')
    assert rv.status_code == 200

def test_project_rdepends_json_200(client):
    rv = client.get('/json/projects/wheel-inspect/rdepends')
    assert rv.status_code == 200

def test_wheel_json_200(client):
    rv = client.get('/json/wheels/wheel_inspect-1.0.0-py3-none-any.whl.json')
    assert rv.status_code == 200
