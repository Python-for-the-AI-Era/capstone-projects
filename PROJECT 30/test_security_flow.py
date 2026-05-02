def test_token_cannot_be_used_twice(db, valid_token_record):
    # First use
    result_1 = verify_and_use_token(db, "raw_secret_123")
    assert result_1 is not None
    
    # Second use (Same token)
    with pytest.raises(SecurityError) as exc:
        verify_and_use_token(db, "raw_secret_123")
    assert "Token already used" in str(exc.value)