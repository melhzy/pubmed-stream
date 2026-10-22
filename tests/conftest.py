import logging
from pathlib import Path
from typing import Callable, Dict, Optional, Union

import pytest
import requests
from requests.adapters import BaseAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def home(tmp_path_factory, monkeypatch):
    """Every test sees an empty home folder, never the developer's own assistant settings."""
    folder = tmp_path_factory.mktemp("home")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: folder))
    monkeypatch.delenv("NCBI_API_KEY", raising=False)             # nor the developer's own key
    monkeypatch.delenv("PUBMED_STREAM_NCBI_API_KEY", raising=False)
    return folder


@pytest.fixture
def full_xml() -> str:
    """Open-access article in JATS 1.0 style (pub-type dates)."""
    return (FIXTURES / "article_full.xml").read_text(encoding="utf-8")


@pytest.fixture
def no_body_xml() -> str:
    """Article whose publisher withholds the XML full text (front matter only)."""
    return (FIXTURES / "article_no_body.xml").read_text(encoding="utf-8")


@pytest.fixture
def elink_json() -> str:
    """ELink neighbor_score response for seed PMID 100."""
    return (FIXTURES / "elink_neighbors.json").read_text(encoding="utf-8")


@pytest.fixture
def pubmed_xml() -> str:
    """EFetch PubMed XML for the seed and its neighbors (PMID 999 is missing)."""
    return (FIXTURES / "pubmed_records.xml").read_text(encoding="utf-8")


class FakeAdapter(BaseAdapter):
    """Answers every request with a canned response, or raises *error*.

    With *routes* ({url substring: body, or callable(request) -> body}), the
    first matching route answers with 200 and unmatched URLs get 404.
    """

    def __init__(
        self,
        status: int = 200,
        body: str = "",
        error: Optional[Exception] = None,
        routes: Optional[Dict[str, Union[str, Callable]]] = None,
    ) -> None:
        super().__init__()
        self.status = status
        self.body = body
        self.error = error
        self.routes = routes
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        status, body = self.status, self.body
        if self.routes is not None:
            body = next((b for key, b in self.routes.items() if key in request.url), None)
            if callable(body):
                body = body(request)
            status, body = (200, body) if body is not None else (404, "")
        resp = requests.Response()
        resp.status_code = status
        resp._content = body.encode("utf-8")
        resp.encoding = "utf-8"
        resp.url = request.url
        resp.request = request
        return resp

    def close(self) -> None:
        pass


@pytest.fixture
def make_session():
    sessions = []

    def factory(**kwargs) -> requests.Session:
        session = requests.Session()
        adapter = FakeAdapter(**kwargs)
        session.mount("https://", adapter)
        session.mount("http://", adapter)   # local services such as Ollama
        sessions.append(session)
        return session

    yield factory
    for session in sessions:
        session.close()


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr("pubmed_stream.downloader.RETRY_DELAY", 0)


@pytest.fixture(autouse=True)
def restore_log_level():
    """CLI tests set the package's log level (--quiet, --verbose); keep it per test."""
    logger = logging.getLogger("pubmed_stream")
    level = logger.level
    yield
    logger.setLevel(level)
