import csv
import logging

from asnake.utils import get_note_text

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging

OUTPUT_HEADERS = [
    "PID",
    "_doi",
    "Collection 1 > Value > Value",
    "Abstract 1 > Value",
    "Abstract 2 > Value",
    "Collection 1 > Archival Series 1 > Part 1 > Title",
    "Collection 1 > Archival Series 1 > Part 2 > Title",
    "Date Created 1 > End Date",
    "Date Created 1 > Single or Start Date",
    "Date Created 1 > Type",
    "Date Created Textual 1 > Value",
    "Location 1 > Shelf Location 1 > Box Number",
    "Title 1 > Non-Sort Portion",
    "Title 1 > Sort Portion",
    "archivesspace_identifier-1:archivesspace_identifier_value",
    "note-1:note_type",
    "note-1:note_value",
]

COLLECTION_NAME = "Bob Fass Recordings and Papers, 1935-2011, bulk 1963-1991"

# Maps output CSV column names to AoJsonParser attribute names.
PARSER_FIELD_MAP = {
    "Abstract 1 > Value": "abstract_1_value",
    "Abstract 2 > Value": "abstract_2_value",
    "Collection 1 > Archival Series 1 > Part 1 > Title": "series_title",
    "Collection 1 > Archival Series 1 > Part 2 > Title": "subseries_title",
    "Date Created 1 > End Date": "date_end",
    "Date Created 1 > Single or Start Date": "date_begin",
    "Date Created 1 > Type": "date_type",
    "Date Created Textual 1 > Value": "date_expression",
    "Location 1 > Shelf Location 1 > Box Number": "box_numbers",
    "Title 1 > Non-Sort Portion": "title_non_sort",
    "Title 1 > Sort Portion": "title_sort",
    "archivesspace_identifier-1:archivesspace_identifier_value": "ao_refid",
}

LEADING_ARTICLES = {"a", "the"}


class HyacinthMetadataUpdater:
    """Updates Hyacinth metadata from ArchivesSpace archival object records.

    Reads an input CSV of DOIs, fetches the corresponding archival object
    data from ArchivesSpace, and writes a new CSV with flattened metadata
    fields for import into Hyacinth.
    """

    def __init__(self, mode="dev"):
        configure_logging(f"hyacinth_metadata_updater_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)
        self.repo = self.as_client.aspace.repositories(self.as_client.RBML_REPO_ID)

    def run(self, original_spreadsheet, output_spreadsheet):
        """Process all rows in the input spreadsheet and write to the output spreadsheet.

        Args:
            original_spreadsheet (str): Path to the input CSV file
            output_spreadsheet (str): Path to the output CSV file
        """
        with open(original_spreadsheet, "r") as infile, open(
            output_spreadsheet, "w"
        ) as outfile:
            reader = csv.DictReader(infile)
            writer = csv.DictWriter(outfile, fieldnames=OUTPUT_HEADERS)
            writer.writeheader()
            for original_row in reader:
                doi = original_row.get("_doi", "n/a")
                try:
                    row = self.process_row(original_row)
                    if row:
                        writer.writerow(row)
                except Exception as e:
                    logging.error(
                        f"Failed to read or write row with DOI {doi}. Error: {e}"
                    )

    def process_row(self, original_row):
        """Process a single row from the input spreadsheet into an output row.

        Args:
            original_row (dict): A row from the input CSV as a dict

        Returns:
            dict: Output row dict, or None if processing fails
        """
        doi = original_row.get("_doi", "n/a")
        try:
            ao_json = self.get_ao_from_doi(original_row["_doi"])
            parser = AoJsonParser(self.as_client, ao_json)
            parser.parse()
        except Exception as e:
            logging.error(f"Failed to process row with DOI {doi}. Error: {e}")
            return None

        row = {
            "PID": original_row["PID"],
            "_doi": original_row["_doi"],
            "Collection 1 > Value > Value": COLLECTION_NAME,
            "note-1:note_type": "BF number",
            "note-1:note_value": parser.bf_numbers,
        }
        row.update(
            {col: getattr(parser, attr, "") for col, attr in PARSER_FIELD_MAP.items()}
        )
        return row

    def get_ao_from_doi(self, doi):
        """Use a DOI to find a digital object and return its linked archival
        object JSON with resolved top containers."""
        search_query = f"{doi.split(':')[-1]} primary_type:digital_object"
        results = list(self.repo.search.with_params(q=search_query))
        if len(results) != 1:
            raise ValueError(f"{len(results)} results found for {doi}")

        dao_json = self.as_client.aspace.client.get(results[0].uri).json()
        ao_uri = dao_json["linked_instances"][0]["ref"]
        return self.as_client.aspace.client.get(
            ao_uri, params={"resolve[]": "top_container"}
        ).json()


class AoJsonParser:
    """Parses a resolved ArchivesSpace archival object JSON into flat fields."""

    def __init__(self, as_client, ao_json):
        self.as_client = as_client
        self.ao_json = ao_json

    def parse(self):
        """Parse the archival object JSON into flat metadata attributes.

        Raises:
            Exception: If any parsing step fails
        """
        try:
            self.abstract_1_value = self._get_note_content("scopecontent")
            self.abstract_2_value = self._get_note_content("processinfo")
            self.series_title = self._get_ancestor_display_string(-2)
            self.subseries_title = (
                self._get_ancestor_display_string(-3)
                if len(self.ao_json["ancestors"]) > 2
                else ""
            )
            self.date_end = self._get_date_field("end")
            self.date_begin = self._get_date_field("begin")
            self.date_type = self._get_date_type()
            self.date_expression = self._get_date_field("expression")
            self.box_numbers = self._get_instance_indicators(
                lambda sub: sub["top_container"]["_resolved"]["indicator"]
            )
            self.bf_numbers = self._get_instance_indicators(
                lambda sub: sub.get("indicator_2")
            )
            self.title_non_sort, self.title_sort = self._split_title()
            self.ao_refid = self.ao_json["ref_id"]
        except Exception as e:
            raise Exception(e) from e

    def _get_note_content(self, note_type):
        """Return the first text content of the first note matching note_type."""
        notes = [n for n in self.ao_json["notes"] if n["type"] == note_type]
        if notes:
            return get_note_text(notes[0], self.as_client.aspace.client)[0]
        return ""

    def _get_ancestor_display_string(self, index):
        """Fetch and return the display_string of an ancestor at the given index."""
        uri = self.ao_json["ancestors"][index]["ref"]
        return self.as_client.aspace.client.get(uri).json()["display_string"]

    def _get_date_field(self, field):
        """Return a field from the first date sub-object, or '' if absent."""
        if self.ao_json.get("dates"):
            return self.ao_json["dates"][0].get(field, "")
        return ""

    def _get_date_type(self):
        """Return 'approximate' if the date expression contains 'circa', else ''."""
        expression = self._get_date_field("expression")
        return "approximate" if "circa" in expression else ""

    def _get_instance_indicators(self, extract_fn):
        """Collect and join indicators from sub_containers using extract_fn."""
        indicators = []
        for instance in self.ao_json["instances"]:
            sub = instance.get("sub_container")
            if sub:
                indicator = extract_fn(sub)
                if indicator is not None:
                    indicators.append(indicator)
        return " ; ".join(indicators)

    def _split_title(self):
        """Split a title into (non-sort, sort) portions based on leading articles."""
        words = self.ao_json["title"].split(" ")
        if words[0].lower() in LEADING_ARTICLES:
            return words[0], " ".join(words[1:])
        return "", " ".join(words)
