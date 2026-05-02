@pytest.mark.anyio
async def test_checkout_insufficient_stock(client, user_token):
    """
    BUSINESS RULE: Users cannot buy more than what's in stock.
    Scenario: Product has 2 items. User tries to buy 5.
    """
    # 1. Setup: Create product with stock=2
    # 2. Action: POST /orders with quantity=5
    # 3. Assertion:
    assert response.status_code == 400
    assert "Insufficient stock" in response.json()["detail"]