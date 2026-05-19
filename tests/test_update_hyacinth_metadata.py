import pytest

from scripts.update_hyacinth_metadata import AoJsonParser, HyacinthMetadataUpdater


@pytest.fixture
def mock_as_client(mocker):
    return mocker.Mock()


@pytest.fixture
def parser(mock_as_client):
    ao_json = {}
    return AoJsonParser(mock_as_client, ao_json)


@pytest.fixture
def updater(mock_aspace, mock_config, mocker):
    mocker.patch("scripts.update_hyacinth_metadata.configure_logging")
    return HyacinthMetadataUpdater("dev")


def test__split_title_with_leading_article(parser):
    parser.ao_json["title"] = "The Kingston Trio"

    result = parser._split_title()

    assert result[0] == "The"
    assert result[1] == "Kingston Trio"


def test__split_title_without_leading_article(parser):
    parser.ao_json["title"] = "Patti Smith"

    result = parser._split_title()

    assert result[0] == ""
    assert result[1] == "Patti Smith"


def test__get_date_field(parser):
    parser.ao_json["dates"] = [
        {"expression": "1943", "begin": "1943", "date_type": "single"}
    ]

    expression_result = parser._get_date_field("expression")
    begin_result = parser._get_date_field("begin")
    end_result = parser._get_date_field("end")

    assert expression_result == "1943"
    assert begin_result == "1943"
    assert not end_result


def test__get_date_field_no_dates(parser):
    result = parser._get_date_field("expression")
    assert result == ""


def test__get_date_type_approximate(parser):
    parser.ao_json["dates"] = [
        {
            "expression": "circa 1950s",
            "begin": "1950",
            "end": "1959",
            "date_type": "inclusive",
        }
    ]

    result = parser._get_date_type()

    assert result == "approximate"


def test__get_date_type_exact(parser):
    parser.ao_json["dates"] = [
        {
            "expression": "1950s",
            "begin": "1950",
            "end": "1959",
            "date_type": "inclusive",
        }
    ]

    result = parser._get_date_type()
    assert result == ""


def test_process_row(updater, mocker):
    mocker.patch.object(updater, "get_ao_from_doi", return_value={})
    parsed = mocker.Mock()
    parsed.abstract_1_value = "Scope Note"
    parsed.abstract_2_value = ""
    parsed.series_title = "Series I"
    parsed.subseries_title = ""
    parsed.date_end = "1955"
    parsed.date_begin = "1950"
    parsed.date_type = "approximate"
    parsed.date_expression = "circa early 1950s"
    parsed.box_numbers = "1"
    parsed.bf_numbers = "123"
    parsed.title_non_sort, parsed.title_sort = "", "Patti Smith"
    parsed.ao_refid = "abc123"
    mocker.patch("scripts.update_hyacinth_metadata.AoJsonParser", return_value=parsed)

    original_row = {
        "_doi": "doi:10.7916/80ss-9f29",
        "PID": "cul:cjsxksn28p",
    }

    processed_row = updater.process_row(original_row)

    assert isinstance(processed_row, dict)
    assert (
        processed_row["Collection 1 > Value > Value"]
        == "Bob Fass Recordings and Papers, 1935-2011, bulk 1963-1991"
    )
    assert processed_row["Abstract 1 > Value"] == "Scope Note"
    assert processed_row["PID"] == "cul:cjsxksn28p"
    assert processed_row["_doi"] == "doi:10.7916/80ss-9f29"
    assert processed_row["Title 1 > Sort Portion"] == "Patti Smith"
    assert processed_row["Title 1 > Non-Sort Portion"] == ""


def test_process_row_failed(updater, mocker):
    mocker.patch.object(
        updater, "get_ao_from_doi", side_effect=ValueError("0 results found for doi")
    )

    original_row = {
        "_doi": "doi:10.7916/80ss-9f29",
        "PID": "cul:cjsxksn28p",
    }

    assert updater.process_row(original_row) is None


def test_get_ao_from_doi(updater, mocker):
    mock_result_json = {"result": "1"}
    mock_result = mocker.Mock()
    mock_result.json.return_value = mock_result_json

    updater.repo.search.with_params.return_value = [mock_result]

    mock_dao_json = {
        "linked_instances": [{"ref": "/repositories/2/archival_objects/456"}]
    }
    mock_ao_json = {"uri": "/repositories/2/archival_objects/456", "ref_id": "abc123"}

    mock_get_dao = mocker.Mock()
    mock_get_dao.json.return_value = mock_dao_json

    mock_get_ao = mocker.Mock()
    mock_get_ao.json.return_value = mock_ao_json

    updater.as_client.aspace.client.get.side_effect = [mock_get_dao, mock_get_ao]

    result = updater.get_ao_from_doi("doi:10.7916/80ss-9f29")
    assert result == mock_ao_json


def test_get_ao_from_doi_no_results(updater):
    updater.repo.search.with_params.return_value = []
    with pytest.raises(ValueError, match="0 results found for doi:10.7916/80ss-9f29"):
        updater.get_ao_from_doi("doi:10.7916/80ss-9f29")
