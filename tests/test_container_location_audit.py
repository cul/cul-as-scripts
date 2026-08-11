from csv import DictReader

import pytest

from scripts.container_location_audit import (
    FULLY_OFFSITE,
    FULLY_ONSITE,
    NOT_INDICATED,
    PARTIALLY_OFFSITE,
    ContainerLocationAuditor,
    _is_enumerated,
    classify_location,
)


@pytest.mark.parametrize(
    "sentence, expected",
    [
        ("Boxes 1-5 are located off-site.", True),
        ("Box 9 is located off-site.", True),
        ("Boxes CC1-CC11 are located on site.", True),
        (
            "The following boxes are located offsite: 1-52.",
            True,
        ),
        ("This collection is located off-site.", False),
        ("The boxes are located off-site.", False),
    ],
)
def test_is_enumerated(sentence, expected):
    assert _is_enumerated(sentence) == expected


@pytest.mark.parametrize(
    "notes, expected_label",
    [
        (["This collection is located off-site."], FULLY_OFFSITE),
        (["Boxes 1-5 are located off-site."], PARTIALLY_OFFSITE),
        (["Boxes CC1-CC11 are located on site."], PARTIALLY_OFFSITE),
        (["This collection is located on-site."], FULLY_ONSITE),
        (["All records are restricted for 25 years."], NOT_INDICATED),
        ([], NOT_INDICATED),
    ],
)
def test_classify_location_rules(notes, expected_label):
    label, _ = classify_location(notes)
    assert label == expected_label


@pytest.mark.parametrize(
    "notes, expected_label",
    [
        (
            [
                "This collection is located off-site.",
                "Digital surrogates are available onsite via links in the container list.",
            ],
            FULLY_OFFSITE,
        ),
        (
            [
                "This collection is located on-site.",
                "This collection is located off-site.",
            ],
            PARTIALLY_OFFSITE,
        ),
        (
            [
                "This collection is located off-site.",
                "This collection is located on-site.",
            ],
            PARTIALLY_OFFSITE,
        ),
        (
            ["This collection is located off-site. Boxes 1-5 are located off-site."],
            PARTIALLY_OFFSITE,
        ),
        (
            [
                "This collection is located off-site.",
                "A 46-box undescribed addition that is not processed exists.",
            ],
            FULLY_OFFSITE,
        ),
    ],
)
def test_classify_location_hazards(notes, expected_label):
    label, _ = classify_location(notes)
    assert label == expected_label


def test_matched_sentences_no_duplicate_on_enumerated_offsite():
    _, matched = classify_location(["Boxes 1-5 are located off-site."])
    assert matched == ["Boxes 1-5 are located off-site."]


def test_matched_sentences_captures_both_in_contradiction():
    _, matched = classify_location(
        [
            "This collection is located off-site.",
            "This collection is located on-site.",
        ]
    )
    assert len(matched) == 2


def test_matched_sentences_empty_when_not_indicated():
    _, matched = classify_location(["All records are restricted for 25 years."])
    assert matched == []


@pytest.fixture
def auditor(mock_aspace, mock_config, mocker):
    mocker.patch("scripts.container_location_audit.configure_logging")
    return ContainerLocationAuditor("dev")


def _fake_container(mocker, barcode="", location_refs=None):
    """Build a fake top container for _tally_containers.

    Args:
        barcode (str): barcode value ("" for none).
        location_refs (list): location URIs, e.g. ["/locations/2"]; None -> no
            locations. Each becomes an object exposing `.ref`.
    """
    tc = mocker.Mock()
    tc.barcode = barcode
    tc.container_locations = [mocker.Mock(ref=r) for r in (location_refs or [])]
    return tc


def test_tally_containers_all_four_buckets(auditor, mocker):
    containers = [
        _fake_container(mocker, barcode="RS00340316"),  # -> Has Barcode
        _fake_container(mocker, barcode="RS00340317"),  # -> Has Barcode
        _fake_container(
            mocker, location_refs=["/locations/7620"]
        ),  # -> Location No Barcode
        _fake_container(mocker, location_refs=["/locations/2"]),  # -> ReCAP No Barcode
        _fake_container(mocker),  # -> No Location No Barcode
    ]
    mocker.patch.object(
        auditor.as_client, "get_top_containers_for_resource", return_value=containers
    )
    resource = mocker.Mock(id_0="4077597")

    tally = auditor._tally_containers(resource)

    assert tally["Total Containers"] == 5
    assert tally["Has Barcode"] == 2
    assert tally["Location No Barcode"] == 1
    assert tally["ReCAP No Barcode"] == 1
    assert tally["No Location No Barcode"] == 1

    sub_counts = {
        column: count for column, count in tally.items() if column != "Total Containers"
    }
    assert sum(sub_counts.values()) == tally["Total Containers"]


def test_tally_containers_empty(auditor, mocker):
    mocker.patch.object(
        auditor.as_client, "get_top_containers_for_resource", return_value=[]
    )
    tally = auditor._tally_containers(mocker.Mock(id_0="1"))
    assert tally == {
        "Total Containers": 0,
        "Has Barcode": 0,
        "Location No Barcode": 0,
        "No Location No Barcode": 0,
        "ReCAP No Barcode": 0,
    }


def test_accessrestrict_texts_filters_by_type(auditor, mocker):
    access_note = mocker.Mock()
    access_note.json.return_value = {"type": "accessrestrict"}
    other_note = mocker.Mock()
    other_note.json.return_value = {"type": "scopecontent"}

    mocker.patch(
        "scripts.container_location_audit.get_note_text",
        side_effect=[["This collection is located\noff-site."]],
    )
    resource = mocker.Mock(notes=[access_note, other_note])

    result = auditor._accessrestrict_texts(resource)

    assert result == ["This collection is located off-site."]


def test_extent_summary_joins_nonempty(auditor, mocker):
    extent1 = mocker.Mock()
    extent1.json.return_value = {"container_summary": "51 record cartons"}
    extent2 = mocker.Mock()
    extent2.json.return_value = {}
    extent3 = mocker.Mock()
    extent3.json.return_value = {"container_summary": "1 flat box"}
    resource = mocker.Mock(extents=[extent1, extent2, extent3])

    assert auditor._extent_summary(resource) == "51 record cartons | 1 flat box"


def test_audit_resource_row_shape(auditor, mocker):
    mocker.patch(
        "scripts.container_location_audit.classify_location",
        return_value=(FULLY_OFFSITE, ["This collection is located off-site."]),
    )
    mocker.patch.object(
        auditor,
        "_accessrestrict_texts",
        return_value=["This collection is located off-site."],
    )
    mocker.patch.object(
        auditor,
        "_tally_containers",
        return_value={
            "Total Containers": 1,
            "Has Barcode": 0,
            "Location No Barcode": 1,
            "No Location No Barcode": 0,
            "ReCAP No Barcode": 0,
        },
    )
    mocker.patch.object(auditor, "_extent_summary", return_value="1 box")
    resource = mocker.Mock(
        uri="/repositories/2/resources/1", id_0="123", title="Test papers"
    )

    row = auditor._audit_resource(resource)

    assert set(row.keys()) == set(ContainerLocationAuditor.FIELDNAMES)
    assert row["Access Restriction Location"] == "fully off-site"
    assert row["Matched Location Sentence"] == "This collection is located off-site."
    assert row["URI"] == "/repositories/2/resources/1"


def test_run_writes_row_per_resource(auditor, tmp_path, mocker):
    resources = [mocker.Mock(), mocker.Mock()]
    mocker.patch.object(
        auditor.as_client, "published_resources", return_value=resources
    )
    row_1 = {"URI": "/repositories/2/resources/1"}
    row_2 = {"URI": "/repositories/2/resources/2"}
    mocker.patch.object(
        auditor,
        "_audit_resource",
        side_effect=[row_1, row_2],
    )
    out = tmp_path / "audit.csv"

    auditor.run(out)

    rows = list(DictReader(open(out, newline="")))
    assert len(rows) == 2


def test_run_skips_failing_resource(auditor, tmp_path, mocker):
    success, failure = mocker.Mock(), mocker.Mock()
    mocker.patch.object(
        auditor.as_client, "published_resources", return_value=[failure, success]
    )
    row = {"URI": "/repositories/2/resources/1"}
    mocker.patch.object(
        auditor,
        "_audit_resource",
        side_effect=[Exception("Error"), row],
    )
    out = tmp_path / "audit.csv"

    auditor.run(out)

    rows = list(DictReader(open(out, newline="")))
    assert len(rows) == 1
