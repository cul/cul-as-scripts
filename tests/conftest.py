import pytest


@pytest.fixture
def mock_aspace(mocker):
    return mocker.patch("scripts.aspace_client.ASpace")


@pytest.fixture
def mock_config(mocker):
    mock = mocker.patch("scripts.aspace_client.ConfigParser")
    mock.return_value.get.side_effect = lambda section, key: {
        ("ArchivesSpace", "dev_baseurl"): "https://sandbox.archivesspace.org/api/",
        ("ArchivesSpace", "username"): "admin",
        ("ArchivesSpace", "password"): "pass",
    }[(section, key)]
    return mock
