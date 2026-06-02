from csv import DictReader

import pytest

from scripts.add_locations import AddLocations
from scripts.helpers import construct_rbml_location, write_data_to_csv


@pytest.fixture
def location_adder(mock_aspace, mock_config, mocker):
    mocker.patch("scripts.add_locations.configure_logging")
    return AddLocations("dev")


def test_get_location_one_result(location_adder, mocker):
    mock_result = mocker.Mock()
    mock_result.uri = "/locations/1"
    location_adder.repo.search.with_params.return_value = [mock_result]
    result = location_adder.get_location("Stack 1", "2e", "3", "4")
    assert result == "/locations/1"


def test_get_location_no_result(location_adder, mocker):
    location_adder.repo.search.with_params.return_value = []
    result = location_adder.get_location("Stack 1", "2e", "3", "4")
    assert not result


def test_get_location_multiple_results(location_adder, mocker):
    mock_result = mocker.Mock()
    mock_result.uri = "/locations/1"
    location_adder.repo.search.with_params.return_value = [mock_result, mock_result]
    with pytest.raises(
        Exception,
        match="More than one result found for Stack 1, 2e, 3, 4",
    ):
        location_adder.get_location("Stack 1", "2e", "3", "4")


def test_create_locations_from_textfile(location_adder, tmp_path, mocker):
    input_file = tmp_path / "text_file.txt"
    input_file.write_text("14, 22e, 01, 01\n14, 23w, 06, 02\n14, 35e, 07, 03")

    mocker.patch.object(location_adder, "get_location", return_value=False)
    location_adder.as_client.aspace.client.post.return_value = mocker.Mock()

    location_adder.create_locations_from_textfile(input_file)

    assert location_adder.as_client.aspace.client.post.call_count == 3
    location_adder.as_client.aspace.client.post.assert_any_call(
        "/locations", json=construct_rbml_location("Stack 14", "22e", "1", "1")
    )
    location_adder.as_client.aspace.client.post.assert_any_call(
        "/locations", json=construct_rbml_location("Stack 14", "23w", "6", "2")
    )
    location_adder.as_client.aspace.client.post.assert_any_call(
        "/locations", json=construct_rbml_location("Stack 14", "35e", "7", "3")
    )


def test_create_locations_location_exists(location_adder, tmp_path, mocker):
    input_file = tmp_path / "text_file.txt"
    input_file.write_text("14, 22e, 01, 0")

    mocker.patch.object(location_adder, "get_location", return_value="/locations/1")

    location_adder.create_locations_from_textfile(input_file)

    location_adder.as_client.aspace.client.post.assert_not_called()


def test_create_locations_error(location_adder, tmp_path, mocker):
    input_file = tmp_path / "text_file.txt"
    input_file.write_text("14, 22e, 01, 0")

    mocker.patch.object(
        location_adder,
        "get_location",
        side_effect=Exception("More than one result found"),
    )

    mock_error = mocker.patch("scripts.add_locations.logging.error")

    location_adder.create_locations_from_textfile(input_file)

    mock_error.assert_called_once()


def test_create_project_spreadsheet(location_adder, tmp_path, mocker, monkeypatch):
    monkeypatch.chdir(tmp_path)
    csv_path = tmp_path / "csv_name.csv"
    sheet_data = [
        ["Location"],
        ["14, 48w, 06, 04"],
        ["14, 48w, 06, 05"],  # for exists in ASpace
        ["14/63w/03 / 04"],
        ["15, 57e&w, 04, 03"],
    ]
    write_data_to_csv(sheet_data, csv_path)

    mocker.patch.object(
        location_adder,
        "get_location",
        side_effect=["/locations/123", False],
    )

    location_adder.create_project_spreadsheet("csv_name.csv")

    with open("stack_14_locations.csv", "r") as f:
        reader = DictReader(f)
        rows = [x for x in reader]
        assert len(rows) == 3
        for row in rows:
            assert len(row) == 2
        assert rows[0]["as_location_id"] == "123"
        for row in rows[1:]:
            assert row["as_location_id"] == "NOT FOUND"
