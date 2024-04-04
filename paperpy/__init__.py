"""paper-py - A python package to access paperless-ng databases."""

import os

# fmt: off
__project__ = 'paperpy'
__version__ = '0.3.0'
# fmt: on

VERSION = __project__ + "-" + __version__

script_dir = os.path.dirname(__file__)

try:
    AUTH_TOKEN = os.environ["PAPERLESS_AUTH_TOKEN"]
    SERVER_URL = os.environ["PAPERLESS_SERVER_URL"]
except:
    print("Server URL and API authorization token was not")
    print("found in environment variables:")
    print("  PAPERLESS_SERVER_URL, PAPERLESS_AUTH_TOKEN")
    exit()

TAG_COLOUR = "#FF6030"
CORR_COLOUR = "#F0D0A0"
DOC_COLOUR = "#30C0A0"
TITLE_COLOUR = "#20A0F0"
DATE_COLOUR = "#AFA0E0"

from .paperpy import (
    PaperDoc,
    PaperClient,
    PaperTag,
    PaperItem,
    PaperCorrespondent,
    PaperDocType,
    merge_docs,
)
