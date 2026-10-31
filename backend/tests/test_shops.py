"""Each synthetic persona shop has isolated records, selected by the X-Munim-Shop header."""

from tests.conftest import key


def test_shops_are_isolated(client):
    tea = {"X-Munim-Shop": "tea_stall"}
    created = client.post("/products", headers=tea, json={"name": "Chai Patti", "unit": "kg", "confirmed": True,
                                                          "idempotency_key": key()})
    assert created.status_code == 201
    assert client.get("/products/resolve", params={"query": "Chai Patti"}, headers=tea).json()["status"] == "RESOLVED"
    assert client.get("/products/resolve", params={"query": "Chai Patti"}).json()["status"] == "NOT_FOUND"
    pid = created.json()["product_id"]
    assert client.get(f"/inventory/products/{pid}/stock").status_code == 404
    assert client.get(f"/inventory/products/{pid}/stock", headers=tea).status_code == 200
    assert client.get("/events", headers=tea).json()[0]["event_type"] == "PRODUCT_CREATED"
    assert client.get("/events").json() == []


def test_unknown_shop_rejected(client):
    assert client.get("/events", headers={"X-Munim-Shop": "someone_else"}).status_code == 400
