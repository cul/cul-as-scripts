import logging

from asnake.utils import walk_tree

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging, construct_digital_instance


class AddIiifDigitalObjects:
    """Creates and attaches IIIF digital objects to ArchivesSpace archival objects."""

    def __init__(self, mode="dev"):
        configure_logging(f"add_iiif_daos_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)

    def run_with_refids(self, list_of_ref_ids, repo_id):
        """Processes a list of ArchivesSpace ref IDs to create and attach
        digital objects to their corresponding archival objects.

        For each ref ID, it fetches the archival objects, creates a new
        digital object pointing to a generated IIIF manifest URL, and attaches
        this digital object as an instance to the archival object.

        Args:
            list_of_ref_ids (list): A list of ArchivesSpace ref IDs
                                    (strings) for Archival Objects to process.
        """
        for ref_id in list_of_ref_ids:
            try:
                ao_json = self.as_client.get_ao_by_ref_id(repo_id, ref_id)
                self.add_do_to_ao(ao_json)
            except Exception as e:
                logging.error(f"{ref_id}: {e}")

    def run_all_series(self, series_id):
        """Add IIIF digital objects to all archival objects in a series.

        Args:
            series_id (int): ASpace archival object ID of the series
        """
        series = self.as_client.aspace.repositories(2).archival_objects(series_id)
        tree = walk_tree(series, self.as_client.aspace.client)
        next(tree)
        for ao_json in tree:
            try:
                self.add_do_to_ao(ao_json)
            except Exception as e:
                logging.error(f"{ao_json['uri']}: {e}")

    def add_do_to_ao(self, ao_json):
        """Create a IIIF digital object and attach it to an archival object.

        Args:
            ao_json (dict): ArchivesSpace archival object JSON
        """
        title = ao_json.get("title") or ao_json.get("display_string")
        digital_object_uri = self.as_client.create_digital_object(
            title,
            f"https://dlc.library.columbia.edu/iiif/3/presentation/aspace/{ao_json['ref_id']}/collection",
        )
        dao = construct_digital_instance(digital_object_uri)
        ao_json["instances"].append(dao)
        response = self.as_client.aspace.client.post(ao_json["uri"], json=ao_json)
        if not response.ok:
            print(ao_json["uri"])
            print(response.status_code, response.reason)
        else:
            logging.info(f"Added DAO to {ao_json['uri']}")
