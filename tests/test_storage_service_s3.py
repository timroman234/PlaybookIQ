import io
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from app.services.storage_service_s3 import S3Storage


@patch("app.services.storage_service_s3.boto3")
def test_put_object_calls_s3_put(mock_boto3):
    mock_client = MagicMock()
    mock_boto3.client.return_value = mock_client

    storage = S3Storage(bucket_name="my-bucket")
    storage.put_object("docs/report.txt", b"hello")

    mock_client.put_object.assert_called_once_with(Bucket="my-bucket", Key="docs/report.txt", Body=b"hello")


@patch("app.services.storage_service_s3.boto3")
def test_get_object_returns_body_bytes(mock_boto3):
    mock_client = MagicMock()
    mock_client.get_object.return_value = {"Body": io.BytesIO(b"hello")}
    mock_boto3.client.return_value = mock_client

    storage = S3Storage(bucket_name="my-bucket")
    result = storage.get_object("docs/report.txt")

    assert result == b"hello"


@patch("app.services.storage_service_s3.boto3")
def test_get_object_missing_key_raises_file_not_found(mock_boto3):
    mock_client = MagicMock()
    mock_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject"
    )
    mock_boto3.client.return_value = mock_client

    storage = S3Storage(bucket_name="my-bucket")
    try:
        storage.get_object("missing.txt")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


@patch("app.services.storage_service_s3.boto3")
def test_list_objects_paginates_and_sorts(mock_boto3):
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {"Contents": [{"Key": "docs/b.txt"}, {"Key": "docs/a.txt"}]},
        {"Contents": [{"Key": "docs/c.txt"}]},
    ]
    mock_client.get_paginator.return_value = mock_paginator
    mock_boto3.client.return_value = mock_client

    storage = S3Storage(bucket_name="my-bucket")
    keys = storage.list_objects("docs/")

    assert keys == ["docs/a.txt", "docs/b.txt", "docs/c.txt"]
    mock_paginator.paginate.assert_called_once_with(Bucket="my-bucket", Prefix="docs/")
