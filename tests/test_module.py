def test_import() -> None:
    import epoa_app

    assert epoa_app
    assert epoa_app.version
