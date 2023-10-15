""" PyPI API client """

from __future__ import annotations
from collections.abc import Callable
import logging
from xmlrpc.client import ProtocolError, ServerProxy
from pypi_simple import ACCEPT_JSON_PREFERRED, PyPISimple
import requests
from tenacity import retry, retry_if_exception, wait_exponential
from .changelog import ChangelogEvent
from .util import USER_AGENT

log = logging.getLogger(__name__)

#: PyPI's XML-RPC and JSON API endpoint
ENDPOINT = "https://pypi.org/pypi"


def on_xml_exception(method: str) -> Callable[[BaseException], bool]:
    """
    If an XML-RPC request fails due to a 5xx error, this function logs the
    event and tells `retrying` to try again.

    :param str method: the name of the XML-RPC method
    """

    def on_exc(e: BaseException) -> bool:
        if isinstance(e, ProtocolError) and 500 <= e.errcode:
            log.warning(
                "XML-RPC request to %s returned %d; retrying", method, e.errcode
            )
            return True
        else:
            return False

    return on_exc


def on_http_exception(e: BaseException) -> bool:
    """
    If an HTTP request fails due to a connection or 5xx error, this function
    logs the event and tells `retrying` to try again.
    """
    if (
        isinstance(e, requests.HTTPError)
        and e.response is not None
        and 500 <= e.response.status_code
    ):
        log.warning(
            "Request to %s returned %d; retrying",
            e.response.request.url,
            e.response.status_code,
        )
        return True
    elif isinstance(e, requests.RequestException):
        log.warning("Request to %s failed: %s: %s", type(e).__name__, str(e))
        return True
    else:
        return False


class PyPIAPI:
    """
    A client for select features of PyPI's APIs with automatic retrying of
    requests that fail due to server errors
    """

    def __init__(self) -> None:
        self.client = ServerProxy(ENDPOINT, use_builtin_types=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT

    @retry(
        retry=retry_if_exception(on_xml_exception("changelog_last_serial")),
        wait=wait_exponential(multiplier=1, max=10),
    )
    def changelog_last_serial(self) -> int:
        """Returns the serial ID of the last event on PyPI"""
        r = self.client.changelog_last_serial()
        assert isinstance(r, int)
        return r

    @retry(
        retry=retry_if_exception(on_http_exception),
        wait=wait_exponential(multiplier=1, max=10),
    )
    def list_packages(self) -> list[str]:
        """Returns a list of the names of all packages on PyPI"""
        # The Warehouse devs prefer it if the Simple API is used for this
        # instead of the XML-RPC API.
        with PyPISimple(accept=ACCEPT_JSON_PREFERRED) as ps:
            return ps.get_index_page().projects

    @retry(
        retry=retry_if_exception(on_http_exception),
        wait=wait_exponential(multiplier=1, max=10),
    )
    def project_data(self, proj: str) -> dict | None:
        """
        Fetch the data for the project ``proj`` from PyPI's JSON API and return
        it.  If the API returns a 404 (which happens when the project has no
        releases), `None` is returned.
        """
        r = self.s.get(f"{ENDPOINT}/{proj}/json")
        if r.status_code == 404:
            # Project has no releases
            return None
        r.raise_for_status()
        data = r.json()
        assert isinstance(data, dict)
        return data

    def asset_data(self, project: str, version: str, filename: str) -> dict | None:
        """
        Query the JSON API for the data on the asset with the given filename
        for the given project & version.  If the asset cannot be found, return
        `None`.
        """
        data = self.project_data(project)
        if data is None:
            return None
        for asset in data.get("releases", {}).get(version, []):
            assert isinstance(asset, dict)
            if asset["filename"] == filename:
                return asset
        return None

    @retry(
        retry=retry_if_exception(on_xml_exception("changelog_since_serial")),
        wait=wait_exponential(multiplier=1, max=10),
    )
    def changelog_since_serial(self, since: int) -> list[ChangelogEvent]:
        """
        Return a list of PyPI changelog entries since the given serial ID
        """
        r = self.client.changelog_since_serial(since)
        assert isinstance(r, list)
        results = []
        for event in r:
            assert isinstance(event, list)
            results.append(ChangelogEvent.parse(event))
        return results
