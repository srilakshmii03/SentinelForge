from demo import register_user


def test_register_user():
    user = register_user("user@example.com", "secret")
    assert user["email"] == "user@example.com"
