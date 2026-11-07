def test_users_domain_package_is_importable() -> None:
    import app.users.domain

    assert app.users.domain is not None
