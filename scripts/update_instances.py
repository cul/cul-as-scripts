import logging

from asnake.utils import walk_tree

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging, construct_instance_with_container


class DisambiguateBoxNums:
    """Disambiguates box numbers in ArchivesSpace by adding a prefix to existing indicators."""

    def __init__(self, mode="dev", repo_id=2):
        configure_logging(f"disambiguate_box_numbers_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)
        self.repo = self.as_client.aspace.repositories(repo_id)

    def process_series(self, resource_identifier, max_box_num, box_prefix, series_uri):
        """Create prefixed top containers and update archival objects in a series.

        For each AO in the series with a single numeric box instance in the
        given range, creates a new prefixed top container and updates the
        AO's instance to point to it.

        Args:
            resource_identifier (str): Collection identifier for top container search
            max_box_num (int): Highest box number to create prefixed containers for
            box_prefix (str): Prefix to prepend to each box indicator (e.g., "FA_")
            series_uri (str): URI of the series to process
        """
        container_list = {}
        for top_container in self.as_client.get_top_containers_for_resource(
            self.repo, resource_identifier
        ):
            container_list[top_container.indicator] = top_container.uri
        box_num_range = range(1, max_box_num + 1)
        for x in box_num_range:
            indicator = f"{box_prefix}{x}"
            top_container_uri = self.as_client.create_top_container(
                self.repo.id, indicator
            )
            container_list[indicator] = top_container_uri
        tree = walk_tree(series_uri, self.as_client.aspace.client)
        next(tree)
        for child in tree:
            try:
                if len(child.get("instances")) == 1:
                    orig_box_uri = child["instances"][0]["sub_container"][
                        "top_container"
                    ]["ref"]
                    orig_box_num = (
                        self.as_client.aspace.client.get(orig_box_uri)
                        .json()
                        .get("indicator")
                    )
                    if orig_box_num and orig_box_num.isnumeric():
                        orig_box_num_int = int(orig_box_num)
                        if orig_box_num_int in box_num_range:
                            new_indicator = f"{box_prefix}{orig_box_num}"
                            box_uri = container_list[new_indicator]
                            new_instance = construct_instance_with_container(box_uri)
                            child["instances"] = [new_instance]
                            self.as_client.aspace.client.post(child["uri"], json=child)
                            logging.info(
                                f"Updated {child['uri']} from box {orig_box_num} to {new_indicator}"
                            )
                        else:
                            logging.warning(
                                f"Could not find new container {new_indicator} for {child['uri']}."
                            )
            except Exception as e:
                logging.error(e)
        logging.info(f"Processing {series_uri} complete.")
