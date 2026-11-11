import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Use a temporary database to protect production data.
    test_db = tmp_path / "test_history.db"
    monkeypatch.setattr(main, "DB_PATH", test_db)

    with TestClient(main.app) as test_client:
        yield test_client


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "watch-history",
        "status": "ok"
    }


def test_get_empty_history(client):
    response = client.get("/history/test_user")

    assert response.status_code == 200
    assert response.json() == []


@patch("main.requests.get")
def test_record_watch_success(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    payload = {
        "user_id": "test_user",
        "movie_id": 1
    }

    response = client.post("/history", json=payload)

    assert response.status_code == 201
    assert response.json()["user_id"] == "test_user"
    assert response.json()["movie_id"] == 1
    assert "watched_at" in response.json()


def test_get_recorded_history(client):
    with patch("main.requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client.post(
            "/history",
            json={"user_id": "test_user", "movie_id": 1}
        )

    response = client.get("/history/test_user")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["movie_id"] == 1


@patch("main.requests.get")
def test_record_nonexistent_movie(mock_get, client):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    response = client.post(
        "/history",
        json={"user_id": "test_user", "movie_id": 99999}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Movie does not exist in the catalog"
    )


@patch("main.requests.get")
def test_catalog_service_unavailable(mock_get, client):
    import requests

    mock_get.side_effect = requests.ConnectionError(
        "Catalog service unavailable"
    )

    response = client.post(
        "/history",
        json={"user_id": "test_user", "movie_id": 1}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Movie Catalog Service is unavailable"
    )


def test_invalid_request_data(client):
    response = client.post(
        "/history",
        json={"user_id": "", "movie_id": 0}
    )

    assert response.status_code == 422
