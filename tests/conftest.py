from pathlib import Path
from typing import Optional

import pytest
import requests
from requests.adapters import BaseAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def full_xml() -> str:
    """Open-access article in JATS 1.0 style (pub-type dates)."""
    return (FIXTURES / "article_full.xml").read_text(encoding="utf-8")


@pytest.fixture
def no_body_xml() -> str:
    """Article whose publisher withholds the XML full text (front matter only)."""
    return (FIXTURES / "article_no_body.xml").read_text(encoding="utf-8")


class FakeAdapter(BaseAdapter):
    """Answers every request with a canned response, or raises *error*."""

    def __init__(self, status: int = 200, body: str = "", error: Optional[Exception] = None) -> None:
        super().__init__()
        self.status = status
        self.body = body
        self.error = error
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        resp = requests.Response()
        resp.status_code = self.status
        resp._content = self.body.encode("utf-8")
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
        session.mount("https://", FakeAdapter(**kwargs))
        sessions.append(session)
        return session

    yield factory
    for session in sessions:
        session.close()


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr("pubmed_stream.downloader.RETRY_DELAY", 0)
