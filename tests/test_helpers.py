import csv

import pytest

from scripts.helpers import (
    collection_matches_series,
    construct_digital_instance,
    construct_external_doc,
    construct_instance_with_container,
    construct_multipart_note,
    create_date_object,
    has_one_series,
    write_data_to_csv,
)


def test_write_data_to_csv(tmp_path):
    csv_path = tmp_path / "csv_name.csv"
    sheet_data = [["Header 1", "Header 2"], ["Row 1", "Row 2"]]
    write_data_to_csv(sheet_data, csv_path)

    with open(csv_path) as f:
        rows = list(csv.reader(f))

    assert rows == sheet_data


@pytest.mark.parametrize(
    "date_string, expected_type, expected_begin, expected_end",
    [
        ("1950", "single", "1950", None),
        ("1950-01", "single", "1950-01", None),
        ("1950-01-01", "single", "1950-01-01", None),
        ("1950-1960", "inclusive", "1950", "1960"),
    ],
)
def test_create_object_valid(date_string, expected_type, expected_begin, expected_end):
    result = create_date_object(date_string)
    assert result["date_type"] == expected_type
    assert result["begin"] == expected_begin
    if expected_end:
        assert result["end"] == expected_end
    else:
        assert "end" not in result


def test_create_object_invalid():
    with pytest.raises(ValueError, match="Unrecognized date format:"):
        create_date_object("Some value")


def test_has_one_series_true():
    assert has_one_series([{"child_count": 4}])


def test_has_one_series_false_no_grandchildren():
    assert not has_one_series([{"child_count": 0}])


def test_has_one_series_false_multiple_children():
    assert not has_one_series([{"child_count": 6}, {"child_count": 2}])


def test_has_one_series_false_empty():
    assert not has_one_series([])


def test_construct_digital_instance():
    result = construct_digital_instance("/repositories/2/digital_objects/1234")
    assert result["digital_object"]["ref"] == "/repositories/2/digital_objects/1234"


def test_construct_external_doc():
    result = construct_external_doc("Inventory", "example.com/inventory")
    assert result["title"] == "Inventory"
    assert result["location"] == "example.com/inventory"
    assert not result["publish"]


def test_construct_instance_with_container():
    container_uri = "/repositories/2/top_containers/1234"
    result = construct_instance_with_container(container_uri)
    assert result["sub_container"]["top_container"]["ref"] == container_uri


def test_construct_multipart_note_published():
    result = construct_multipart_note("accessrestrict", "This collection is open.")
    assert result["publish"]
    assert result["type"] == "accessrestrict"
    assert len(result["subnotes"]) == 1
    assert result["subnotes"][0]["content"] == "This collection is open."
    assert result["subnotes"][0]["publish"]


def test_construct_multipart_note_unpublished():
    result = construct_multipart_note("processinfo", "Internal note.", False)
    assert not result["publish"]
    assert result["type"] == "processinfo"
    assert len(result["subnotes"]) == 1
    assert result["subnotes"][0]["content"] == "Internal note."
    assert not result["subnotes"][0]["publish"]


def test_collection_matches_series():
    collection_title = "Village Green Preservation Society Records"

    for series_title in [
        "Village Green Preservation Society Records",
        "Series I: Village Green Preservation Society Records",
        "Series I. Village Green Preservation Society Records",
    ]:
        assert collection_matches_series(collection_title, series_title)
    assert not collection_matches_series(collection_title, "Series II: Something Else")
