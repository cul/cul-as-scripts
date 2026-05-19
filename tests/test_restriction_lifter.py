from datetime import date

import pytest

from scripts.restriction_lifter import GetAccessNotes


@pytest.fixture
def access_notes(mock_aspace, mock_config, mocker):
    mocker.patch("scripts.restriction_lifter.configure_logging")
    return GetAccessNotes("dev")


def test__get_flagged_notes_match_found(access_notes, mocker):
    mock_note = mocker.Mock()
    mock_note.type = "accessrestrict"

    mock_ao = mocker.Mock()
    mock_ao.notes = [mock_note]

    access_notes.repo.search.with_params.return_value = [mock_ao]

    mocker.patch(
        "scripts.restriction_lifter.get_note_text",
        return_value=["File is closed until 2026."],
    )

    results = list(access_notes._get_flagged_notes(2026))

    assert len(results) == 1
    assert results[0][0] == mock_ao
    assert results[0][1] == [mock_note]


def test__get_flagged_notes_wrong_year(access_notes, mocker):
    mock_note = mocker.Mock()
    mock_note.type = "accessrestrict"

    mock_ao = mocker.Mock()
    mock_ao.notes = [mock_note]

    access_notes.repo.search.with_params.return_value = [mock_ao]

    mocker.patch(
        "scripts.restriction_lifter.get_note_text",
        return_value=["File is closed until 2050."],
    )

    results = list(access_notes._get_flagged_notes(2026))

    assert not results


def test__get_flagged_notes_wrong_note_type(access_notes, mocker):
    mock_note = mocker.Mock()
    mock_note.type = "scopecontent"

    mock_ao = mocker.Mock()
    mock_ao.notes = [mock_note]

    access_notes.repo.search.with_params.return_value = [mock_ao]
    mock_get_note_text = mocker.patch("scripts.restriction_lifter.get_note_text")

    results = list(access_notes._get_flagged_notes(2026))

    assert not results
    mock_get_note_text.assert_not_called()


def test_revision_statement(access_notes):
    today = date.today()
    today_date = today.strftime("%Y-%m-%d")
    result = access_notes.revision_statement(2026)

    assert result["date"] == today_date
    assert result["description"] == "Restrictions expiring in 2026 have been lifted."


def test_create_csv(access_notes, mocker):
    mock_ao = mocker.Mock()
    mock_ao.resource.id = 123
    mock_ao.resource.title = "Village Green Preservation Society Records"
    mock_ao.display_string = "Custard Pie Appreciation Consortium"
    mock_ao.uri = "/repositories/2/archival_objects/1234"

    mock_note = mocker.Mock()
    mock_note.persistent_id = "587ac2b96b3e1ccaf5cbbbe24e6c904a"
    mocker.patch(
        "scripts.restriction_lifter.get_note_text", return_value=["Access restriction."]
    )

    mocker.patch.object(
        access_notes, "_get_flagged_notes", return_value=[(mock_ao, [mock_note])]
    )

    mock_write_data_to_csv = mocker.patch(
        "scripts.restriction_lifter.write_data_to_csv",
    )

    access_notes.repo.name = "CUL"

    access_notes.create_csv(2026)

    mock_write_data_to_csv.assert_called_once_with(
        [
            [
                "id_0",
                "Collection Title",
                "Component Display String",
                "Component URI",
                "Note ID",
                "Note Text",
            ],
            [
                123,
                "Village Green Preservation Society Records",
                "Custard Pie Appreciation Consortium",
                "/repositories/2/archival_objects/1234",
                "587ac2b96b3e1ccaf5cbbbe24e6c904a",
                "Access restriction.",
            ],
        ],
        "accessrestrict_2026_CUL.csv",
    )


def test_remove_restrictions(access_notes, mocker):
    mock_ao = mocker.Mock()
    mock_ao.json.return_value = {
        "notes": [{"persistent_id": "587ac2b96b3e1ccaf5cbbbe24e6c904a"}],
        "uri": "/repositories/2/archival_objects/1234",
    }
    mock_ao.resource.uri = "/repositories/2/resources/123"

    mock_note = mocker.Mock()
    mock_note.persistent_id = "587ac2b96b3e1ccaf5cbbbe24e6c904a"

    mocker.patch.object(
        access_notes, "_get_flagged_notes", return_value=[(mock_ao, [mock_note])]
    )

    mocker.patch(
        "scripts.restriction_lifter.get_note_text",
        return_value=["File is closed until 2026."],
    )

    mock_resource = {
        "title": "Village Green Preservation Society",
        "revision_statements": [],
        "uri": mock_ao.resource.uri,
    }
    access_notes.as_client.aspace.client.get.return_value.json.return_value = (
        mock_resource
    )

    mock_update = mocker.patch.object(access_notes.as_client, "update_aspace_field")

    access_notes.remove_restrictions(2026)

    mock_update.assert_any_call(mock_ao.json.return_value, "notes", [])
    assert len(mock_resource["revision_statements"]) == 1
