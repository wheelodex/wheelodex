import logging
from   xmlrpc.client import ProtocolError, ServerProxy
import requests
from   retrying      import retry

log = logging.getLogger(__name__)

ENDPOINT = 'https://pypi.org/pypi'

def on_xml_exception(method):
    def on_exc(e):
        if isinstance(e, ProtocolError) and 500 <= e.errcode:
            log.warning('XML-RPC request to %s returned %d; retrying',
                        method, e.errcode)
            return True
        else:
            return False
    return on_exc

def on_json_exception(e):
    if isinstance(e, requests.HTTPError) and 500 <= e.response.status_code:
        log.warning('JSON API request returned %d; retrying',
                    e.response.status_code)
        return True
    else:
        return False

class PyPIAPI:
    def __init__(self):
        self.client = ServerProxy(ENDPOINT, use_builtin_types=True)
        self.s = requests.Session()

    @retry(
        retry_on_exception          = on_xml_exception('changelog_last_serial'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def changelog_last_serial(self):
        return self.client.changelog_last_serial()

    @retry(
        retry_on_exception          = on_xml_exception('list_packages'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def list_packages(self):
        return self.client.list_packages()

    @retry(
        retry_on_exception          = on_json_exception,
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def project_data(self, proj):
        r = self.s.get('{}/{}/json'.format(ENDPOINT, proj))
        if r.status_code == 404:
            # Project has no releases
            return None
        r.raise_for_status()
        return r.json()

    @retry(
        retry_on_exception          = on_xml_exception('changelog_since_serial'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def changelog_since_serial(self, since):
        return self.client.changelog_since_serial(since)
