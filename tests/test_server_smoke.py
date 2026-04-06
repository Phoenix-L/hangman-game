import importlib

import pytest


def test_server_app_import_and_root_route():
    """Smoke test: importing server exposes a Flask app and root route responds."""
    flask = pytest.importorskip("flask")
    server = importlib.import_module("server")

    assert hasattr(server, "app")
    assert isinstance(server.app, flask.Flask)

    client = server.app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    response.get_data()
    response.close()
