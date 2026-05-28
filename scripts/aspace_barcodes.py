import csv
import logging

from scripts.aspace_client import ArchivesSpaceClient
from scripts.helpers import configure_logging


class AspaceBarcodeFetcher:
    """Fetches top container barcodes from ArchivesSpace using FOLIO HRIDs."""

    def __init__(self, mode="dev"):
        configure_logging(f"aspace_barcode_fetcher_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)
        self.repo = self.as_client.aspace.repositories(self.as_client.RBML_REPO_ID)

    def run(self, folio_csv_path, output_path):
        """Fetches ASpace barcodes for each unique HRID in the FOLIO CSV.

        Args:
            folio_csv_path (str): Path to the FOLIO barcode CSV.
            output_path (str): Path to the output CSV file.
        """
        hrids = self.get_unique_hrids(folio_csv_path)
        logging.info(f"Found {len(hrids)} unique HRIDs in {folio_csv_path}")
        rows = []
        for hrid in hrids:
            logging.info(f"Processing {hrid}")
            rows.extend(self.get_rows_for_hrid(hrid))
        self.write_csv(rows, output_path)
        logging.info(f"Wrote {len(rows)} rows to {output_path}")

    def get_unique_hrids(self, folio_csv_path):
        """Reads the FOLIO CSV and returns the unique instance HRIDs.

        Args:
            folio_csv_path (str): Path to the FOLIO barcode CSV.

        Returns:
            list[str]: Unique instance HRIDs in the order they appear.
        """
        with open(folio_csv_path, newline="", encoding="utf-8") as f:
            hrids = [row["instance_hrid"] for row in csv.DictReader(f)]
        return list(dict.fromkeys(hrids))

    def get_rows_for_hrid(self, hrid):
        """Fetches top container data for a single HRID.

        Args:
            hrid (str): Instance HRID to use as the collection identifier.

        Returns:
            list[dict]: Rows of top container data for this HRID. Empty if no
                top containers are found in ASpace for the given HRID.
        """
        rows = []
        for top_container in self.as_client.get_top_containers_for_resource(
            self.repo, hrid
        ):
            barcode = getattr(top_container, "barcode", "")
            container_type = getattr(top_container, "type", "")
            rows.append(
                {
                    "instance_hrid": hrid,
                    "container_label": f"{container_type} {top_container.indicator}",
                    "container_barcode": barcode,
                    "container_uri": top_container.uri,
                }
            )
        if not rows:
            logging.warning(f"No ASpace top containers found for HRID {hrid}")
        return rows

    def write_csv(self, rows, output_path):
        """Writes top container rows to a CSV file.

        Args:
            rows (list[dict]): List of row dicts to write.
            output_path (str): Path to the output CSV file.
        """
        fieldnames = [
            "instance_hrid",
            "container_label",
            "container_barcode",
            "container_uri",
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


class AspaceBarcodeUpdater:
    """Adds barcodes to ASpace top containers using information from a spreadsheet."""

    def __init__(self, mode="dev"):
        configure_logging(f"aspace_barcode_updater_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)

    def run(self, input_spreadsheet):
        with open(input_spreadsheet, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    msg = self.add_barcode_to_top_container(
                        row["folio_barcode"], row["aspace_uri"]
                    )
                    logging.info(msg)
                except Exception as e:
                    logging.error(
                        f"Error processing {row['folio_barcode']} in {row['title']}: {e}"
                    )

    def add_barcode_to_top_container(
        self, barcode, top_container_uri, location="/locations/2"
    ):
        top_container_json = self.as_client.aspace.client.get(top_container_uri).json()
        if top_container_json.get("barcode"):
            raise ValueError(f"Top container {top_container_uri} already has barcode.")
        self.as_client.update_aspace_field(top_container_json, "barcode", barcode)
        self.as_client.add_location_to_top_container(top_container_uri, location)
        return f"Successfully added {barcode} and location to {top_container_uri}."
