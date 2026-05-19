import logging

from asnake.utils import walk_tree

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging


class AddContainers:
    """Adds container instance data to archival objects in ArchivesSpace.

    This class provides methods to traverse an ArchivesSpace series or resource
    tree and propagate container instance information from archival
    objects to archival objects that lack instance data.
    """

    def __init__(self, mode="dev", repo_id=2):
        configure_logging(f"add_containers_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)
        self.repo = self.as_client.aspace.repositories(repo_id)

    def run_series(self, series_id):
        """Propagate container instances across all file/item-level AOs in a series.

        Args:
            series_id (int): ASpace archival object ID of the series
        """
        series = self.repo.archival_objects(series_id)
        tree = walk_tree(series, self.as_client.aspace.client)
        next(tree)
        logging.info(f"Updating {series.title}...")
        self.process_tree(tree)

    def run_resource(self, resource_id):
        """Propagate container instances across all file/item-level AOs in a resource.

        Args:
            resource_id (int): ASpace resource ID
        """
        resource = self.as_client.aspace.repositories(2).resources(resource_id)
        tree = walk_tree(resource, self.as_client.aspace.client)
        next(tree)
        logging.info(f"Updating {resource.title}...")
        self.process_tree(tree)

    def process_tree(self, tree):
        """Propagate container instances through a tree of archival objects.

        For file and item-level AOs, copies the most recently seen instance
        data to any AO that has none.

        Args:
            tree (generator): ASnake tree generator yielding archival object dicts
        """
        instances = None
        for ao in tree:
            if ao["level"].lower() in ["file", "item"]:
                if ao["instances"]:
                    instances = ao["instances"]
                else:
                    if instances:
                        self.as_client.update_aspace_field(ao, "instances", instances)
