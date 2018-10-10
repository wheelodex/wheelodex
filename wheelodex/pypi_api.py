""" PyPI API client """

import logging
from   xmlrpc.client import ProtocolError, ServerProxy
import requests
from   retrying      import retry
from   .util         import USER_AGENT

log = logging.getLogger(__name__)

#: PyPI's XML-RPC and JSON API endpoint
ENDPOINT = 'https://pypi.org/pypi'

def on_xml_exception(method):
    """
    If an XML-RPC request fails due to a 5xx error, this function logs the
    event and tells `retrying` to try again.

    :param str method: the name of the XML-RPC method
    """
    def on_exc(e):
        if isinstance(e, ProtocolError) and 500 <= e.errcode:
            log.warning('XML-RPC request to %s returned %d; retrying',
                        method, e.errcode)
            return True
        else:
            return False
    return on_exc

def on_json_exception(e):
    """
    If a JSON API request fails due to a 5xx error, this function logs the
    event and tells `retrying` to try again.
    """
    if isinstance(e, requests.HTTPError) and 500 <= e.response.status_code:
        log.warning('JSON API request returned %d; retrying',
                    e.response.status_code)
        return True
    else:
        return False

class PyPIAPI:
    """
    A client for PyPI's XML-RPC and JSON APIs with automatic retrying of
    requests that fail due to server errors
    """

    def __init__(self):
        self.client = ServerProxy(ENDPOINT, use_builtin_types=True)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT

    @retry(
        retry_on_exception          = on_xml_exception('changelog_last_serial'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def changelog_last_serial(self):
        """ Returns the serial ID of the last event on PyPI """
        return self.client.changelog_last_serial()

    @retry(
        retry_on_exception          = on_xml_exception('list_packages'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def list_packages(self):
        """ Returns a list of the names of all packages on PyPI """
        return self.client.list_packages()

    @retry(
        retry_on_exception          = on_json_exception,
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def project_data(self, proj):
        """
        Fetch the data for the project ``proj`` from PyPI's JSON API and return
        it.  If the API returns a 404 (which happens when the project has no
        releases), `None` is returned.
        """
        r = self.s.get('{}/{}/json'.format(ENDPOINT, proj))
        if r.status_code == 404:
            # Project has no releases
            return None
        r.raise_for_status()
        return r.json()

    def asset_data(self, project, version, filename):
        """
        Query the JSON API for the data on the asset with the given filename
        for the given project & version.  If the asset cannot be found, return
        `None`.
        """
        data = self.project_data(project)
        if data is None:
            return None
        for asset in data.get("releases", {}).get(version, []):
            if asset["filename"] == filename:
                return asset
        return None

    @retry(
        retry_on_exception          = on_xml_exception('changelog_since_serial'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def changelog_since_serial(self, since):
        """
        Return a list of PyPI changelog entries since the given serial ID
        """
        return self.client.changelog_since_serial(since)
