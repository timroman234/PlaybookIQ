from app.services.storage_service import LocalFileStorage


def test_put_get_roundtrip(tmp_path):
    storage = LocalFileStorage(tmp_path)
    storage.put_object("docs/report.txt", b"hello world")

    assert storage.get_object("docs/report.txt") == b"hello world"


def test_list_objects_filters_by_prefix(tmp_path):
    storage = LocalFileStorage(tmp_path)
    storage.put_object("docs/a.txt", b"a")
    storage.put_object("docs/b.txt", b"b")
    storage.put_object("other/c.txt", b"c")

    assert storage.list_objects("docs/") == ["docs/a.txt", "docs/b.txt"]
    assert storage.list_objects() == ["docs/a.txt", "docs/b.txt", "other/c.txt"]


def test_get_object_missing_key_raises(tmp_path):
    storage = LocalFileStorage(tmp_path)

    try:
        storage.get_object("missing.txt")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
