# <https://www.python.org/dev/peps/pep-0503/>
from   urllib.parse import urljoin
from   bs4          import BeautifulSoup
import requests

ENDPOINT = 'https://pypi.python.org/simple/'

def response2soup(r):
    # <http://stackoverflow.com/a/35383883/744178>
    if 'charset' in r.headers.get('content-type', '').lower():
        charset = r.encoding
    else:
        charset = None
    return BeautifulSoup(r.content, 'html.parser', from_encoding=charset)

def get_all_wheels():
    pypi = requests.Session()
    r = pypi.get(ENDPOINT)
    r.raise_for_status()
    index = response2soup(r)
    for link in index.find_all('a'):
        # PEP 503 says "The text of the anchor tag MUST be the normalized name
        # of the project", but PyPI (both legacy and Warehouse) doesn't follow
        # that.
        s = pypi.get(urljoin(r.url, link['href']))
        s.raise_for_status()
        filepage = response2soup(s)
        for flink in filepage.find_all('a'):
            if flink.string.endswith('.whl'):
                yield (flink.string, urljoin(s.url, flink['href']))
                ### Extract & include hash from URL fragment?
