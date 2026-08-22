"""Regression guard: api.vision_routes must actually be reachable through the
live app. A prior bug in api/server.py silently dropped this router from
app.routes after include_router() (a defensive filter assumed every route
object exposes `.path`, which is not true for the router wrapper object
newer FastAPI versions use), 404-ing every route it defines with no test
catching it."""
from fastapi.testclient import TestClient

import api.server as server


def test_vision_router_get_routes_are_reachable():
    client = TestClient(server.app)
    for path in (
        "/api/v1/blocks",
        "/api/v1/scan-runs",
        "/api/v1/events",
        "/api/v1/counts",
        "/api/v1/analytics/summary",
    ):
        response = client.get(path)
        assert response.status_code != 404, f"{path} is not mounted (404)"
