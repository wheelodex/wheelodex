from __future__ import annotations
from collections.abc import Iterator
import json
from pathlib import Path
from flask import current_app
from flask.testing import FlaskClient
import pytest
from sqlalchemy import text
from wheelodex.app import create_app
from wheelodex.models import Project, Wheel, db

DATA_DIR = Path(__file__).with_name("data")


@pytest.fixture(scope="session")
def sampledb() -> Iterator[None]:
    with create_app(TESTING=True).app_context():
        # See <https://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#foreign-key-support>:
        db.session.execute(text("PRAGMA foreign_keys=ON"))
        db.create_all()
        for p in (DATA_DIR / "json-wheels").iterdir():
            with p.open(encoding="utf-8") as fp:
                Wheel.add_from_json(json.load(fp))
        Project.ensure("no-wheels")
        db.session.commit()
        yield


@pytest.fixture()
def client(sampledb: None) -> FlaskClient:  # noqa: U100
    return current_app.test_client()


def test_index_200(client: FlaskClient) -> None:
    rv = client.get("/")
    assert rv.status_code == 200


def test_robots_txt(client: FlaskClient) -> None:
    rv = client.get("/robots.txt")
    assert rv.status_code == 200
    assert rv.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_about_200(client: FlaskClient) -> None:
    rv = client.get("/about/")
    assert rv.status_code == 200


def test_json_api_200(client: FlaskClient) -> None:
    rv = client.get("/json-api/")
    assert rv.status_code == 200


def test_recent_wheels_200(client: FlaskClient) -> None:
    rv = client.get("/recent/")
    assert rv.status_code == 200


def test_rdepends_leaders_200(client: FlaskClient) -> None:
    rv = client.get("/rdepends-leaders/")
    assert rv.status_code == 200


def test_project_list_200(client: FlaskClient) -> None:
    rv = client.get("/projects/")
    assert rv.status_code == 200
    assert "wheel-inspect" in rv.text


def test_project_200(client: FlaskClient) -> None:
    rv = client.get("/projects/wheel-inspect/")
    assert rv.status_code == 200


def test_project_nonnormalized(client: FlaskClient) -> None:
    rv = client.get("/projects/Wheel.Inspect/", follow_redirects=False)
    assert rv.status_code == 301
    assert rv.location == "/projects/wheel-inspect/"


def test_project_nonexistent(client: FlaskClient) -> None:
    rv = client.get("/projects/not-found/")
    assert rv.status_code == 404


def test_wheel_data_200(client: FlaskClient) -> None:
    rv = client.get(
        "/projects/wheel-inspect/wheels/wheel_inspect-1.0.0-py3-none-any.whl/"
    )
    assert rv.status_code == 200


def test_wheel_data_nonnormalized(client: FlaskClient) -> None:
    rv = client.get(
        "/projects/Wheel.Inspect/wheels/wheel_inspect-1.0.0-py3-none-any.whl/",
        follow_redirects=False,
    )
    assert rv.status_code == 301
    assert (
        rv.location
        == "/projects/wheel-inspect/wheels/wheel_inspect-1.0.0-py3-none-any.whl/"
    )


def test_wheel_data_nonexistent(client: FlaskClient) -> None:
    rv = client.get("/projects/not-found/wheels/not_found-1.0.0-py3-none-any.whl/")
    assert rv.status_code == 404


def test_rdepends_200(client: FlaskClient) -> None:
    rv = client.get("/projects/wheel-inspect/rdepends/")
    assert rv.status_code == 200


def test_entry_point_groups_200(client: FlaskClient) -> None:
    rv = client.get("/entry-points/")
    assert rv.status_code == 200
    assert "console_scripts" in rv.text


def test_entry_point_groups_sortby_qty_200(client: FlaskClient) -> None:
    rv = client.get("/entry-points/", query_string={"sortby": "qty"})
    assert rv.status_code == 200
    assert "console_scripts" in rv.text


def test_entry_point_200(client: FlaskClient) -> None:
    rv = client.get("/entry-points/console_scripts/")
    assert rv.status_code == 200
    data = rv.text
    assert "wheel-inspect" in data
    assert "wheel2json" in data


def test_search_projects_200(client: FlaskClient) -> None:
    rv = client.get("/search/projects/", query_string={"q": "wheel-*"})
    assert rv.status_code == 200
    assert "wheel-inspect" in rv.text


@pytest.mark.skip(reason="SQLite does not support array_agg")
def test_search_files_200(client: FlaskClient) -> None:
    rv = client.get("/search/files/", query_string={"q": "wheel_*"})
    assert rv.status_code == 200
    assert "wheel_inspect" in rv.text


def test_search_modules_200(client: FlaskClient) -> None:
    rv = client.get("/search/modules/", query_string={"q": "wheel_*"})
    assert rv.status_code == 200
    assert "wheel_inspect" in rv.text


def test_search_commands_200(client: FlaskClient) -> None:
    rv = client.get("/search/commands/", query_string={"q": "wheel*"})
    assert rv.status_code == 200
    assert "wheel2json" in rv.text


def test_project_json_200(client: FlaskClient) -> None:
    rv = client.get("/json/projects/wheel-inspect")
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


def test_project_data_json_200(client: FlaskClient) -> None:
    with (DATA_DIR / "json-wheels" / "wheel-inspect.json").open(encoding="utf-8") as fp:
        expected = json.load(fp)
    rv = client.get("/json/projects/wheel-inspect/data")
    assert rv.status_code == 200
    assert rv.get_json() == expected


def test_project_data_json_no_wheels(client: FlaskClient) -> None:
    rv = client.get("/json/projects/no-wheels/data")
    assert rv.status_code == 404
    assert rv.get_json() == {"message": "No wheels found for project"}


def test_project_rdepends_json_200(client: FlaskClient) -> None:
    rv = client.get("/json/projects/wheel-inspect/rdepends")
    assert rv.status_code == 200


def test_wheel_json_200(client: FlaskClient) -> None:
    with (DATA_DIR / "json-wheels" / "wheel-inspect.json").open(encoding="utf-8") as fp:
        expected = json.load(fp)
    rv = client.get("/json/wheels/wheel_inspect-1.0.0-py3-none-any.whl.json")
    assert rv.status_code == 200
    assert rv.get_json() == expected
