"""Store endpoint response parsing. No sockets are opened here."""

from __future__ import annotations

import pytest

from steamview import http, steamstore


class TestParseAppdetails:
    def test_successful_response(self):
        payload = {"1145360": {"success": True, "data": {"name": "Hades"}}}
        assert steamstore.parse_appdetails(payload, 1145360) == {"name": "Hades"}

    def test_a_delisted_app_reports_failure(self):
        assert steamstore.parse_appdetails({"1": {"success": False}}, 1) is None

    def test_the_appid_key_must_match(self):
        payload = {"999": {"success": True, "data": {"name": "Other"}}}
        assert steamstore.parse_appdetails(payload, 1145360) is None

    @pytest.mark.parametrize(
        "payload",
        [None, {}, "junk", 42, [], {"1": None}, {"1": "junk"}, {"1": {"success": True}}, {"1": {"success": True, "data": "junk"}}],
    )
    def test_malformed_payloads_return_none(self, payload):
        assert steamstore.parse_appdetails(payload, 1) is None


class TestParseStoresearch:
    def test_items_are_returned(self):
        payload = {"total": 2, "items": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}
        assert len(steamstore.parse_storesearch(payload)) == 2

    def test_non_dict_items_are_filtered_out(self):
        payload = {"items": [{"id": 1, "name": "A"}, "junk", None, 42]}
        assert steamstore.parse_storesearch(payload) == [{"id": 1, "name": "A"}]

    @pytest.mark.parametrize("payload", [None, {}, "junk", 42, {"items": None}, {"items": "junk"}])
    def test_malformed_payloads_yield_an_empty_list(self, payload):
        assert steamstore.parse_storesearch(payload) == []


class TestFetchAppdetails:
    def test_request_shape(self, monkeypatch):
        seen = {}

        def fake_get_json(url, params=None, timeout=None):
            seen["url"] = url
            seen["params"] = params
            return {"1145360": {"success": True, "data": {"name": "Hades"}}}

        monkeypatch.setattr(steamstore.http, "get_json", fake_get_json)
        assert steamstore.fetch_appdetails(1145360) == {"name": "Hades"}
        assert seen["url"] == steamstore.APPDETAILS_URL
        assert seen["params"] == {"appids": 1145360, "l": "english", "cc": "us"}

    def test_a_network_failure_returns_none(self, monkeypatch):
        monkeypatch.setattr(steamstore.http, "get_json", lambda *a, **k: None)
        assert steamstore.fetch_appdetails(1145360) is None

    @pytest.mark.parametrize("appid", [0, -1, None, "1145360"])
    def test_invalid_appids_never_hit_the_network(self, appid, monkeypatch):
        def explode(*args, **kwargs):
            raise AssertionError("network must not be touched")

        monkeypatch.setattr(steamstore.http, "get_json", explode)
        assert steamstore.fetch_appdetails(appid) is None


class TestSearchStore:
    def test_request_shape(self, monkeypatch):
        seen = {}

        def fake_get_json(url, params=None, timeout=None):
            seen["url"] = url
            seen["params"] = params
            return {"items": [{"id": 1091500, "name": "Cyberpunk 2077"}]}

        monkeypatch.setattr(steamstore.http, "get_json", fake_get_json)
        assert steamstore.search_store("Cyberpunk 2077") == [{"id": 1091500, "name": "Cyberpunk 2077"}]
        assert seen["url"] == steamstore.STORESEARCH_URL
        assert seen["params"] == {"term": "Cyberpunk 2077", "cc": "us", "l": "english"}

    @pytest.mark.parametrize("term", ["", "   ", None])
    def test_a_blank_term_never_hits_the_network(self, term, monkeypatch):
        def explode(*args, **kwargs):
            raise AssertionError("network must not be touched")

        monkeypatch.setattr(steamstore.http, "get_json", explode)
        assert steamstore.search_store(term) == []

    def test_a_network_failure_yields_an_empty_list(self, monkeypatch):
        monkeypatch.setattr(steamstore.http, "get_json", lambda *a, **k: None)
        assert steamstore.search_store("Hades") == []


class TestBuildUrl:
    def test_params_are_encoded(self):
        assert http.build_url("https://x/api", {"term": "a b"}) == "https://x/api?term=a+b"

    def test_none_values_are_omitted(self):
        assert http.build_url("https://x/api", {"a": 1, "b": None}) == "https://x/api?a=1"

    def test_an_existing_query_string_is_extended(self):
        assert http.build_url("https://x/api?z=1", {"a": 2}) == "https://x/api?z=1&a=2"

    @pytest.mark.parametrize("params", [None, {}])
    def test_no_params_leaves_the_url_untouched(self, params):
        assert http.build_url("https://x/api", params) == "https://x/api"


class TestHttpFailureHandling:
    """The HTTP layer must degrade to ``None``/``False``, never raise."""

    def test_a_transport_error_is_retried_then_gives_up(self, monkeypatch):
        import urllib.error

        attempts = []

        def explode(*args, **kwargs):
            attempts.append(1)
            raise urllib.error.URLError("no route to host")

        monkeypatch.setattr(http._opener, "open", explode)
        assert http.get_json("https://x/api", sleep=lambda _: None) is None
        assert len(attempts) == http._MAX_ATTEMPTS

    def test_rate_limiting_is_retried(self, monkeypatch):
        import io
        import urllib.error

        calls = []

        class Response:
            headers = {}
            status = 200

            def read(self, *_):
                return b'{"ok": true}'

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise urllib.error.HTTPError("https://x", 429, "Too Many", {"Retry-After": "0"}, io.BytesIO(b""))
            return Response()

        monkeypatch.setattr(http._opener, "open", flaky)
        assert http.get_json("https://x/api", sleep=lambda _: None) == {"ok": True}
        assert len(calls) == 2

    def test_a_404_is_not_retried(self, monkeypatch):
        import io
        import urllib.error

        calls = []

        def not_found(*args, **kwargs):
            calls.append(1)
            raise urllib.error.HTTPError("https://x", 404, "Not Found", {}, io.BytesIO(b""))

        monkeypatch.setattr(http._opener, "open", not_found)
        assert http.get_json("https://x/api", sleep=lambda _: None) is None
        assert len(calls) == 1

    def test_an_unparseable_body_returns_none(self, monkeypatch):
        class Response:
            headers = {}

            def read(self, *_):
                return b"<html>nope</html>"

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        monkeypatch.setattr(http._opener, "open", lambda *a, **k: Response())
        assert http.get_json("https://x/api", sleep=lambda _: None) is None

    def test_url_exists_is_true_for_a_2xx(self, monkeypatch):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        monkeypatch.setattr(http._opener, "open", lambda *a, **k: Response())
        assert http.url_exists("https://cdn/microtrailer.webm") is True

    def test_url_exists_is_false_for_a_404(self, monkeypatch):
        import io
        import urllib.error

        def not_found(*args, **kwargs):
            raise urllib.error.HTTPError("https://cdn", 404, "Not Found", {}, io.BytesIO(b""))

        monkeypatch.setattr(http._opener, "open", not_found)
        assert http.url_exists("https://cdn/microtrailer.webm") is False

    def test_url_exists_is_false_when_the_transport_fails(self, monkeypatch):
        import urllib.error

        def explode(*args, **kwargs):
            raise urllib.error.URLError("offline")

        monkeypatch.setattr(http._opener, "open", explode)
        assert http.url_exists("https://cdn/microtrailer.webm") is False
