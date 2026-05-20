import csv

import pytest

from scripts.aspace_barcodes import AspaceBarcodeFetcher, AspaceBarcodeUpdater
from scripts.helpers import write_data_to_csv


@pytest.fixture
def barcode_fetcher(mock_aspace, mock_config, mocker):
    mocker.patch("scripts.aspace_barcodes.configure_logging")
    return AspaceBarcodeFetcher("dev")


@pytest.fixture
def barcode_updater(mock_aspace, mock_config, mocker):
    mocker.patch("scripts.aspace_barcodes.configure_logging")
    return AspaceBarcodeUpdater("dev")


def test_get_unique_hrids(barcode_fetcher, tmp_path):
    csv_path = tmp_path / "csv_name.csv"
    sheet_data = [
        ["instance_hrid", "item_barcode"],
        ["14364697", "RS01663127"],
        ["4079637", "RS00751804"],
        ["4079637", "RS00751812"],
    ]
    write_data_to_csv(sheet_data, csv_path)

    result = barcode_fetcher.get_unique_hrids(csv_path)

    assert len(result) == 2
    assert result[0] == "14364697"
    assert result[1] == "4079637"


def test_get_rows_for_hrid_containers(barcode_fetcher, mocker):
    mock_container_1 = mocker.Mock()
    mock_container_1.barcode = "RS00123456"
    mock_container_1.type = "box"
    mock_container_1.indicator = "1"
    mock_container_1.uri = "/repositories/2/top_containers/123"

    mock_container_2 = mocker.Mock()
    mock_container_2.barcode = ""
    mock_container_2.type = "box"
    mock_container_2.indicator = "2"
    mock_container_2.uri = "/repositories/2/top_containers/124"

    mocker.patch.object(
        barcode_fetcher.as_client,
        "get_top_containers_for_resource",
        return_value=[mock_container_1, mock_container_2],
    )

    result = barcode_fetcher.get_rows_for_hrid("in123456")

    assert len(result) == 2
    assert result[0]["container_label"] == "box 1"
    assert result[0]["container_barcode"] == "RS00123456"
    assert len(result[0].keys()) == 4
    assert result[1]["container_barcode"] == ""


def test_get_rows_for_hrid_no_containers(barcode_fetcher, mocker):
    mocker.patch.object(
        barcode_fetcher.as_client,
        "get_top_containers_for_resource",
        return_value=[],
    )
    mock_warning = mocker.patch("scripts.aspace_barcodes.logging.warning")

    barcode_fetcher.get_rows_for_hrid("in123456")

    mock_warning.assert_called_once_with(
        "No ASpace top containers found for HRID in123456"
    )


def test_write_csv(barcode_fetcher, tmp_path):
    rows = [
        {
            "instance_hrid": "in123456",
            "container_label": "box 1",
            "container_barcode": "RS00123456",
            "container_uri": "/repositories/2/top_containers/124",
        }
    ]

    csv_path = tmp_path / "csv_name.csv"

    barcode_fetcher.write_csv(rows, csv_path)

    with open(csv_path) as f:
        written_data = list(csv.reader(f))

    assert written_data[0] == [
        "instance_hrid",
        "container_label",
        "container_barcode",
        "container_uri",
    ]
    assert written_data[1] == [
        "in123456",
        "box 1",
        "RS00123456",
        "/repositories/2/top_containers/124",
    ]


def test_add_barcode_to_top_container_no_barcode(barcode_updater, mocker):
    top_container_json = {"uri": "/repositories/2/top_containers/1"}
    mock_top_container = mocker.Mock()
    mock_top_container.json.return_value = top_container_json

    barcode_updater.as_client.aspace.client.get.return_value = mock_top_container

    result = barcode_updater.add_barcode_to_top_container(
        "123456789", "/repositories/2/top_containers/1"
    )

    assert result == "Successfully added 123456789 to /repositories/2/top_containers/1."


def test_add_barcode_to_top_container_with_barcode(barcode_updater, mocker):
    top_container_json = {
        "uri": "/repositories/2/top_containers/1",
        "barcode": "987654321",
    }
    mock_top_container = mocker.Mock()
    mock_top_container.json.return_value = top_container_json

    barcode_updater.as_client.aspace.client.get.return_value = mock_top_container

    with pytest.raises(
        ValueError,
        match="Top container /repositories/2/top_containers/1 already has barcode.",
    ):
        barcode_updater.add_barcode_to_top_container(
            "123456789", "/repositories/2/top_containers/1"
        )


def test_run(barcode_updater, mocker, tmp_path):
    csv_path = tmp_path / "barcodes.csv"
    write_data_to_csv(
        [
            ["instance_hrid", "folio_barcode", "aspace_uri"],
            ["in1234567", "UA00012345", "/repositories/2/top_containers/1"],
            ["in1234567", "UA00054321", "/repositories/2/top_containers/2"],
        ],
        csv_path,
    )

    mocker.patch.object(
        barcode_updater,
        "add_barcode_to_top_container",
        side_effect=[
            "Successfully added UA00012345 to /repositories/2/top_containers/1.",
            ValueError(
                "Top container /repositories/2/top_containers/2 already has barcode."
            ),
        ],
    )

    mock_info = mocker.patch("scripts.aspace_barcodes.logging.info")
    mock_error = mocker.patch("scripts.aspace_barcodes.logging.error")

    barcode_updater.run(csv_path)

    mock_info.assert_called_once_with(
        "Successfully added UA00012345 to /repositories/2/top_containers/1."
    )
    mock_error.assert_called_once_with(
        "Error processing UA00054321 in in1234567: "
        "Top container /repositories/2/top_containers/2 already has barcode."
    )
