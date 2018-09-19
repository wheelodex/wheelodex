import logging
from   xmlrpc.client import ProtocolError, ServerProxy
from   retrying      import retry

log = logging.getLogger(__name__)

ENDPOINT = 'https://pypi.org/pypi'

def on_exception(method):
    def on_exc(e):
        if isinstance(e, ProtocolError) and 500 <= e.errcode:
            log.warning('XML-RPC request to %s returned %d; retrying',
                        method, e.errcode)
            return True
        else:
            return False
    return on_exc

class PyPIXMLRPC:
    def __init__(self):
        self.client = ServerProxy(ENDPOINT, use_builtin_types=True)

    @retry(
        retry_on_exception          = on_exception('changelog_last_serial'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def changelog_last_serial(self):
        return self.client.changelog_last_serial()

    @retry(
        retry_on_exception          = on_exception('list_packages'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def list_packages(self):
        return self.client.list_packages()

    @retry(
        retry_on_exception          = on_exception('package_releases'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def package_releases(self, pkg):
        return self.client.package_releases(pkg, True)

    @retry(
        retry_on_exception          = on_exception('release_urls'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def release_urls(self, pkg, version):
        return self.client.release_urls(pkg, version)

    @retry(
        retry_on_exception          = on_exception('changelog_since_serial'),
        wait_exponential_multiplier = 1000,
        wait_exponential_max        = 10000,
    )
    def changelog_since_serial(self, since):
        return self.client.changelog_since_serial(since)
