""" An index of wheels """

try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version

__version__      = version('wheelodex')
__author__       = 'John Thorvald Wodder II'
__author_email__ = 'wheelodex@varonathe.org'
__license__      = 'MIT'
__url__          = 'https://github.com/jwodder/wheelodex'
