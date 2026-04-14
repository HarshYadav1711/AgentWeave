"""
Demo-ready checks for AgentWeave (run locally: ``pip install -r requirements-dev.txt`` then ``pytest``).

Each test is named for interview walkthroughs: what it proves is obvious from the name.
"""

from __future__ import annotations


def test_add_agent_success(client):
    r = client.post(
        "/agents",
        json={
            "name": "Alpha",
            "description": "First demo agent",
            "endpoint": "http://localhost:7001",
            "tags": ["demo"],
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body.get("ok") is True
    assert body["name"] == "Alpha"
    assert "demo" in body["tags"]


def test_search_by_keyword_in_name(client):
    client.post(
        "/agents",
        json={
            "name": "SearchableNameToken",
            "description": "plain",
            "endpoint": "http://localhost:7001",
        },
    )
    r = client.get("/search", params={"q": "token"})
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert "SearchableNameToken" in names


def test_search_by_keyword_in_description(client):
    client.post(
        "/agents",
        json={
            "name": "Beta",
            "description": "Handles galaxy routing for workloads",
            "endpoint": "http://localhost:7002",
        },
    )
    r = client.get("/search", params={"q": "galaxy"})
    assert r.status_code == 200
    names = [a["name"] for a in r.json()]
    assert "Beta" in names


def test_log_usage_success(client):
    client.post(
        "/agents",
        json={"name": "Caller", "description": "c", "endpoint": "http://c"},
    )
    client.post(
        "/agents",
        json={"name": "Target", "description": "t", "endpoint": "http://t"},
    )
    r = client.post(
        "/usage",
        json={
            "caller": "Caller",
            "target": "Target",
            "units": 3.0,
            "request_id": "req-demo-1",
        },
    )
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j["status"] == "recorded"
    assert j["units"] == 3.0


def test_duplicate_request_id_ignored_and_totals_unchanged(client):
    client.post(
        "/agents",
        json={"name": "A", "description": "", "endpoint": "http://a"},
    )
    client.post(
        "/agents",
        json={"name": "B", "description": "", "endpoint": "http://b"},
    )
    payload = {
        "caller": "A",
        "target": "B",
        "units": 5.0,
        "request_id": "idem-1",
    }
    first = client.post("/usage", json=payload)
    assert first.status_code == 200
    assert first.json()["status"] == "recorded"

    second = client.post("/usage", json=payload)
    assert second.status_code == 200
    j = second.json()
    assert j["status"] == "ignored"
    assert j.get("ignored_duplicate_request") is True
    assert j["operation"] == "ignored_duplicate_request"

    summary = client.get("/usage-summary").json()
    rows = {row["target"]: row["total_units"] for row in summary["by_target"]}
    assert rows.get("B") == 5.0


def test_usage_unknown_caller_returns_error(client):
    client.post(
        "/agents",
        json={"name": "OnlyTarget", "description": "", "endpoint": "http://x"},
    )
    r = client.post(
        "/usage",
        json={
            "caller": "Nobody",
            "target": "OnlyTarget",
            "units": 1.0,
            "request_id": "r1",
        },
    )
    assert r.status_code == 404
    assert r.json().get("ok") is False
    assert r.json()["error"] == "caller_not_found"


def test_usage_unknown_target_returns_error(client):
    client.post(
        "/agents",
        json={"name": "OnlyCaller", "description": "", "endpoint": "http://x"},
    )
    r = client.post(
        "/usage",
        json={
            "caller": "OnlyCaller",
            "target": "Nobody",
            "units": 1.0,
            "request_id": "r2",
        },
    )
    assert r.status_code == 404
    assert r.json().get("ok") is False
    assert r.json()["error"] == "target_not_found"


def test_missing_fields_validation_error(client):
    r = client.post("/usage", json={"caller": "X"})
    assert r.status_code == 422
    body = r.json()
    assert body.get("ok") is False
    assert body["error"] == "validation_error"


def test_invalid_units_validation_error(client):
    client.post(
        "/agents",
        json={"name": "A", "description": "", "endpoint": "http://a"},
    )
    client.post(
        "/agents",
        json={"name": "B", "description": "", "endpoint": "http://b"},
    )
    r = client.post(
        "/usage",
        json={
            "caller": "A",
            "target": "B",
            "units": 0,
            "request_id": "bad-units",
        },
    )
    assert r.status_code == 422
    assert r.json().get("ok") is False


def test_usage_summary_correct_totals(client):
    client.post(
        "/agents",
        json={"name": "X", "description": "", "endpoint": "http://x"},
    )
    client.post(
        "/agents",
        json={"name": "Y", "description": "", "endpoint": "http://y"},
    )
    client.post(
        "/agents",
        json={"name": "Z", "description": "", "endpoint": "http://z"},
    )
    client.post(
        "/usage",
        json={
            "caller": "X",
            "target": "Y",
            "units": 2.0,
            "request_id": "u1",
        },
    )
    client.post(
        "/usage",
        json={
            "caller": "Z",
            "target": "Y",
            "units": 3.0,
            "request_id": "u2",
        },
    )
    client.post(
        "/usage",
        json={
            "caller": "Y",
            "target": "Z",
            "units": 1.0,
            "request_id": "u3",
        },
    )

    r = client.get("/usage-summary")
    assert r.status_code == 200
    summary = r.json()
    assert summary.get("ok") is True
    rows = {row["target"]: row["total_units"] for row in summary["by_target"]}
    assert rows["Y"] == 5.0
    assert rows["Z"] == 1.0
    # Highest usage first (Y before Z)
    assert [row["target"] for row in summary["by_target"]] == ["Y", "Z"]
