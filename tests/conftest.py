"""Shared fixtures. All network access is mocked -- tests never touch it.

This file also carries a ~15-line async-test runner. The plugin has zero
Python dependencies by design, and that includes the test suite: rather
than pull in ``pytest-asyncio`` just to await a handful of coroutines, a
``pytest_pyfunc_call`` hook runs them on a fresh event loop. CI then needs
nothing but ``pytest`` itself.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from steamview.cache import MediaCache


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: run this coroutine test on a fresh event loop")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Run ``async def`` tests, so no async plugin is needed."""
    test = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test):
        return None
    kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(test(**kwargs))
    return True


@pytest.fixture
def clock():
    """A manually advanced clock, so TTL tests do not sleep."""

    class Clock:
        def __init__(self) -> None:
            self.now = 1_000_000.0

        def __call__(self) -> float:
            return self.now

        def advance(self, seconds: float) -> None:
            self.now += seconds

    return Clock()


@pytest.fixture
def cache(tmp_path, clock):
    return MediaCache(str(tmp_path / "media"), clock=clock)


@pytest.fixture
def appdetails_payload():
    """A realistic ``appdetails`` ``data`` block."""
    return {
        "name": "Hades",
        "header_image": "https://cdn.akamai.steamstatic.com/steam/apps/1145360/header.jpg",
        "movies": [
            {
                "id": 256811033,
                "name": "Launch Trailer",
                "thumbnail": "http://cdn.akamai.steamstatic.com/steam/apps/256811033/movie.293x165.jpg",
                "webm": {
                    "480": "http://cdn.akamai.steamstatic.com/steam/apps/256811033/movie480_vp9.webm",
                    "max": "http://cdn.akamai.steamstatic.com/steam/apps/256811033/movie_max_vp9.webm",
                },
                "mp4": {
                    "480": "http://cdn.akamai.steamstatic.com/steam/apps/256811033/movie480.mp4",
                    "max": "http://cdn.akamai.steamstatic.com/steam/apps/256811033/movie_max.mp4",
                },
                "highlight": True,
            }
        ],
        "screenshots": [
            {"id": 0, "path_thumbnail": "http://cdn/ss_0.116x65.jpg", "path_full": "http://cdn/ss_0.1920x1080.jpg"},
            {"id": 1, "path_thumbnail": "http://cdn/ss_1.116x65.jpg", "path_full": "http://cdn/ss_1.1920x1080.jpg"},
        ],
    }


class FakeStore:
    """Stand-in for :mod:`steamview.steamstore` with scripted responses."""

    def __init__(self, appdetails=None, searches=None):
        self.appdetails = appdetails or {}
        self.searches = searches or {}
        self.appdetails_calls: list[int] = []
        self.search_calls: list[str] = []

    def fetch_appdetails(self, appid, timeout=None):
        self.appdetails_calls.append(appid)
        return self.appdetails.get(appid)

    def search_store(self, term, timeout=None):
        self.search_calls.append(term)
        return self.searches.get(term, [])


@pytest.fixture
def fake_store():
    return FakeStore
