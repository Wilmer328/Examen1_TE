import pytest
from fastapi.testclient import TestClient

from common import config, db


@pytest.fixture(scope="session")
def client():
    from backend.app.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def token(client):
    user, pwd, _ = config.APP_USERS.split(",")[0].split(":")
    r = client.post("/api/auth/login", data={"username": user, "password": pwd})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def dw():
    with db.connection(config.DB_DW) as cn:
        yield cn
