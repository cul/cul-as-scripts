import csv

import pytest

from scripts.get_aspace_barcodes import AspaceBarcodeFetcher
from scripts.helpers import write_data_to_csv


@pytest.fixture
def aspace_barcodes(mock_aspace, mock_config, mocker):
    mocker.patch("scripts.get_aspace_barcodes.configure_logging")
    return AspaceBarcodeFetcher("dev")


def test_get_unique_hrids(aspace_barcodes, tmp_path):
    csv_path = tmp_path / "csv_name.csv"
    sheet_data = [
        ["instance_hrid", "item_barcode"],
        ["14364697", "RS01663127"],
        ["4079637", "RS00751804"],
        ["4079637", "RS00751812"],
    ]
    write_data_to_csv(sheet_data, csv_path)

    result = aspace_barcodes.get_unique_hrids(csv_path)

    assert len(result) == 2
    assert result[0] == "14364697"
    assert result[1] == "4079637"


def test_get_rows_for_hrid_containers(aspace_barcodes, mocker):
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
        aspace_barcodes.as_client,
        "get_top_containers_for_resource",
        return_value=[mock_container_1, mock_container_2],
    )

    result = aspace_barcodes.get_rows_for_hrid("in123456")

    assert len(result) == 2
    assert result[0]["container_label"] == "box 1"
    assert result[0]["container_barcode"] == "RS00123456"
    assert len(result[0].keys()) == 4
    assert result[1]["container_barcode"] == ""


def test_get_rows_for_hrid_no_containers(aspace_barcodes, mocker):
    mocker.patch.object(
        aspace_barcodes.as_client,
        "get_top_containers_for_resource",
        return_value=[],
    )
    mock_warning = mocker.patch("scripts.get_aspace_barcodes.logging.warning")

    aspace_barcodes.get_rows_for_hrid("in123456")

    mock_warning.assert_called_once_with(
        "No ASpace top containers found for HRID in123456"
    )


def test_write_csv(aspace_barcodes, tmp_path):
    rows = [
        {
            "instance_hrid": "in123456",
            "container_label": "box 1",
            "container_barcode": "RS00123456",
            "container_uri": "/repositories/2/top_containers/124",
        }
    ]

    csv_path = tmp_path / "csv_name.csv"

    aspace_barcodes.write_csv(rows, csv_path)

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
