import pytest
from   wheelodex.inspect.util import extract_dependencies, extract_modules, \
                                        split_keywords

@pytest.mark.parametrize('kwstr,expected', [
    (
        'pypi,warehouse,search,packages,pip',
        (['pypi', 'warehouse', 'search', 'pip'], ','),
    ),
    (
        'pypi warehouse search packages pip',
        (['pypi', 'warehouse', 'search', 'pip'], ' '),
    ),
    (
        "pypi,pep503,simple repository api,packages,pip",
        (["pypi", "pep503", "simple repository api", "packages", "pip"], ','),
    ),
])
def test_split_keywords(kwstr, expected):
    assert split_keywords(kwstr) == expected

def test_extract_modules():
    assert extract_modules([
        "qypi/__init__.py",
        "qypi/__main__.py",
        "qypi/api.py",
        "qypi/util.py",
        "qypi-0.4.1.dist-info/DESCRIPTION.rst",
        "qypi-0.4.1.dist-info/LICENSE.txt",
        "qypi-0.4.1.dist-info/METADATA",
        "qypi-0.4.1.dist-info/RECORD",
        "qypi-0.4.1.dist-info/WHEEL",
        "qypi-0.4.1.dist-info/entry_points.txt",
        "qypi-0.4.1.dist-info/metadata.json",
        "qypi-0.4.1.dist-info/top_level.txt",
    ]) == ["qypi", "qypi.__main__", "qypi.api", "qypi.util"]

@pytest.mark.parametrize('requires_dist,expected', [
    (
        ["click (~=6.5)", "packaging (>=16)", "requests (==2.*)"],
        ["click", "packaging", "requests"],
    ),

    (
        [
            "requests",
            "docutils",
            "requests_download",
            "zipfile36; python_version in \"3.3 3.4 3.5\""
        ],
        ["docutils", "requests", "requests_download", "zipfile36"],
    )

    (
        [
            "setuptools",
            "Sphinx; extra == 'docs'",
            "repoze.sphinx.autointerface; extra == 'docs'",
            "zope.event; extra == 'test'",
            "coverage; extra == 'testing'",
            "nose; extra == 'testing'",
            "zope.event; extra == 'testing'",
        ],
        [
            "Sphinx",
            "coverage",
            "nose",
            "repoze.sphinx.autointerface",
            "setuptools",
            "zope.event",
        ]
    ),

    (
        [
            "certifi (>=2017.4.17)",
            "chardet (<3.1.0,>=3.0.2)",
            "idna (<2.6,>=2.5)",
            "urllib3 (>=1.21.1,<1.22)",
            "cryptography (>=1.3.4); extra == 'security'",
            "idna (>=2.0.0); extra == 'security'",
            "pyOpenSSL (>=0.14); extra == 'security'",
            "PySocks (!=1.5.7,>=1.5.6); extra == 'socks'",
            "win-inet-pton; sys_platform == \"win32\" and (python_version == \"2.7\" or python_version == \"2.6\") and extra == 'socks'",
        ],
        [
            "PySocks",
            "certifi",
            "chardet",
            "cryptography",
            "idna",
            "pyOpenSSL",
            "urllib3",
            "win-inet-pton",
        ],
    )
])
def test_extract_dependencies(requires_dist, expected):
    assert extract_dependencies(requires_dist) == expected

### TODO: Add more test cases for all functions!
