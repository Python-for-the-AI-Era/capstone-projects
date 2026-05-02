import pytest

# Day 2: Happy Path - Create a Product
@pytest.mark.anyio
async def test_create_product_success(client, admin_token):
    payload = {"name": "iPhone 15", "price": 1200000, "stock": 10}
    response = await client.post("/products", json=payload, headers={"Authorization": admin_token})
    
    assert response.status_code == 201
    assert response.json()["name"] == "iPhone 15"

# Day 3: Error Path - Unauthenticated Access
@pytest.mark.anyio
async def test_create_product_unauthorized(client):
    payload = {"name": "Illegal Item", "price": 0}
    response = await client.post("/products", json=payload) # No token
    
    assert response.status_code == 401