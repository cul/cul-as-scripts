import pytest

from scripts.aspace_client import ArchivesSpaceClient


@pytest.fixture
def client(mock_aspace, mock_config, mocker):
    mocker.patch("scripts.aspace_client.ArchivesSpaceClient")
    return ArchivesSpaceClient()


def test_initialization(mock_aspace, mock_config):
    ArchivesSpaceClient()
    mock_aspace.assert_called_once_with(
        baseurl="https://sandbox.archivesspace.org/api/",
        username="admin",
        password="pass",
    )


def test_get_digital_objects(client, mocker):
    do_json = {"digital_object_id": "cc6fb25eb6b0034c0c9ec14178a27607d"}
    mock_do = mocker.Mock()
    mock_do.json.return_value = do_json

    client.aspace.repositories.return_value.search.with_params.return_value = [mock_do]

    result = client.get_digital_objects(2)

    assert list(result) == [do_json]


def test_get_ead(client, mocker):
    mock_response = mocker.Mock()
    mock_response.content = b"<ead>Content</ead>"
    client.aspace.client.get.return_value = mock_response

    result = client.get_ead(2, 1234)

    assert result == "<ead>Content</ead>"
    client.aspace.client.get.assert_called_once_with(
        "/repositories/2/resource_descriptions/1234.xml",
        params={"include_unpublished": False, "include_daos": True},
    )


def test_published_resources(client, mocker):
    mock_resource_published = mocker.Mock()
    mock_resource_published.publish = True
    mock_resource_published.suppressed = False
    mock_resource_unpublished = mocker.Mock()
    mock_resource_unpublished.publish = False
    mock_resource_unpublished.suppressed = False
    mock_resource_supppressed = mocker.Mock()
    mock_resource_supppressed.publish = True
    mock_resource_supppressed.suppressed = True

    client.aspace.repositories.return_value.resources = [
        mock_resource_published,
        mock_resource_unpublished,
        mock_resource_supppressed,
    ]

    results = list(client.published_resources(2))
    assert len(results) == 1
    assert results[0] == mock_resource_published


def test_get_ao_by_ref_id_result(client, mocker):
    find_by_refid_response_json_resolved = {
        "archival_objects": [
            {
                "ref": "/repositories/2/archival_objects/1234",
                "_resolved": {"ref_id": "abcd1234"},
            }
        ]
    }
    mock_response = mocker.Mock()
    mock_response.json.return_value = find_by_refid_response_json_resolved
    client.aspace.client.get.return_value = mock_response

    result = client.get_ao_by_ref_id(2, "abcd1234")

    assert result == {"ref_id": "abcd1234"}
    client.aspace.client.get.assert_called_once_with(
        "/repositories/2/find_by_id/archival_objects?ref_id[]=abcd1234"
    )


def test_get_ao_by_ref_id_no_result(client, mocker):
    find_by_refid_response_json_resolved = {"archival_objects": []}

    mock_response = mocker.Mock()
    mock_response.json.return_value = find_by_refid_response_json_resolved
    client.aspace.client.get.return_value = mock_response

    with pytest.raises(ValueError, match="No results found for refid"):
        client.get_ao_by_ref_id(2, "abcd1234")


def test_get_all_aos_in_resource_default(client, mocker):
    client.aspace.repositories.return_value.search.with_params.return_value = [
        mocker.Mock()
    ]

    list(client.get_all_aos_in_resource(1234))

    client.aspace.repositories.return_value.search.with_params.assert_called_once_with(
        q='primary_type:archival_object AND resource:"/repositories/2/resources/1234"',
    )


def test_get_all_aos_in_resource_explicit_repo_id(client, mocker):
    client.aspace.repositories.return_value.search.with_params.return_value = [
        mocker.Mock()
    ]

    list(client.get_all_aos_in_resource(1234, repo_id=3))

    client.aspace.repositories.return_value.search.with_params.assert_called_once_with(
        q='primary_type:archival_object AND resource:"/repositories/3/resources/1234"',
    )


def test_get_call_num_with_user_defined(client, mocker):
    resource = mocker.Mock()
    resource.user_defined.string_1 = "MS#1234"

    result = client.get_call_num(resource)

    assert result == "MS#1234"


def test_get_call_num_no_user_defined(client, mocker):
    resource = mocker.Mock()
    del resource.user_defined

    result = client.get_call_num(resource)

    assert result == ""


def test_update_aspace_field(client):
    resource_json = {"uri": "/repositories/2/resources/213", "title": "Old Title"}

    client.update_aspace_field(resource_json, "title", "New Title")

    assert resource_json["title"] == "New Title"
    client.aspace.client.post.assert_called_once_with(
        "/repositories/2/resources/213", json=resource_json
    )


def test_create_top_container(client):
    client.aspace.client.post.return_value.json.return_value = {
        "uri": "/repositories/2/top_containers/123"
    }

    result = client.create_top_container(2, 1)

    assert result == "/repositories/2/top_containers/123"
    client.aspace.client.post.assert_called_once_with(
        "/repositories/2/top_containers",
        json={
            "jsonmodel_type": "top_container",
            "indicator": 1,
            "type": "box",
        },
    )


def test_create_top_containers_range(client, mocker):
    mocker.patch.object(
        client,
        "create_top_container",
        side_effect=[
            "/repositories/2/top_containers/123",
            "/repositories/2/top_containers/124",
            "/repositories/2/top_containers/125",
        ],
    )

    result = client.create_top_containers_range(2, 50, 52)

    assert result == {
        "50": "/repositories/2/top_containers/123",
        "51": "/repositories/2/top_containers/124",
        "52": "/repositories/2/top_containers/125",
    }


def test_strip_parens_from_content(client, mocker):
    ao_json = {
        "uri": "/repositories/2/resources/123",
        "notes": [{"subnotes": [{"content": "(2 folders)"}]}],
    }

    mocker.patch.object(client, "update_aspace_field")

    client.strip_parens_from_content(ao_json)

    assert ao_json["notes"][0]["subnotes"][0]["content"] == "2 folders"
    client.update_aspace_field.assert_called_once_with(
        ao_json, "notes", ao_json["notes"]
    )


def test_get_resource_children(client, mocker):
    waypoint_response_json = [{"child_count": 6}]
    mock_response = mocker.Mock()
    mock_response.json.return_value = waypoint_response_json
    client.aspace.client.get.return_value = mock_response

    result = client.get_resource_children("/repositories/2/resources/123")
    assert result == waypoint_response_json


def test_add_child_to_resource(client):
    resource_uri = "/repositories/2/resources/123"
    ao_uri = "/repositories/2/archival_objects/1234"
    position = 10
    client.add_child_to_resource(resource_uri, ao_uri, position)
    client.aspace.client.post.assert_called_once_with(
        "/repositories/2/resources/123/accept_children",
        params={
            "children[]": "/repositories/2/archival_objects/1234",
            "position": 10,
        },
    )
