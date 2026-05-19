import logging

from asnake.utils import walk_tree

from .aspace_client import ArchivesSpaceClient
from .helpers import collection_matches_series, configure_logging, has_one_series


class GetOneSeries:
    """Identifies resources that have exactly one series with children."""

    def __init__(self, mode="dev", repo_id=2):
        configure_logging(f"get_one_series_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)

    def run(self):
        """Print a report of resources with exactly one series across all published repositories."""
        for repo in self.as_client.published_repositories():
            for resource in self.as_client.published_resources(repo.id):
                children = self.as_client.get_resource_children(resource.uri)
                if has_one_series(children):
                    print(
                        f"{repo.name}\t{resource.title}\t{children[0]['title']}\t{self.has_notes(children[0]['uri'])}"
                    )

    def has_notes(self, ao_uri):
        ao_json = self.as_client.aspace.client.get(ao_uri).json()
        return bool(ao_json.get("notes"))


class RemoveOneSeries:
    """Removes redundant single-series structure from ArchivesSpace resources."""

    def __init__(self, mode="dev"):
        configure_logging(f"remove_one_series_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)

    def run(self, repo_id=2):
        """Remove redundant single-series structure from published resources in a repository.

        For each resource with exactly one series, moves the series' direct
        children up to the resource level and deletes the series if its title
        matches the collection or it has no notes.

        Args:
            repo_id (int): ASpace repository ID. Defaults to 2.
        """
        count = 0
        for resource in self.as_client.published_resources(repo_id):
            count += 1
            if count % 100 == 0:
                logging.info(f"Iterated through {count} resources")
            try:
                children = self.as_client.get_resource_children(resource.uri)
                if not has_one_series(children):
                    continue
                series = self.as_client.aspace.repositories(repo_id).archival_objects(
                    int(children[0]["uri"].split("/")[-1])
                )
                title_matches = collection_matches_series(resource.title, series.title)
                series_has_notes = len(series.notes) > 0
                if not title_matches and not series_has_notes:
                    continue
                logging.info(f"Removing {series.title} from {resource.title}")
                tree = walk_tree(series, self.as_client.aspace.client)
                next(tree)
                position = 0
                for child in tree:
                    if child["parent"]["ref"] == series.uri:
                        self.as_client.add_child_to_resource(
                            resource.uri, child["uri"], position
                        )
                        position += 1
                logging.info(f"Added {position} children to {resource.title}")
                self.as_client.delete_in_aspace(series.uri)
            except Exception as e:
                logging.error(f"Error while processing {resource.title}: {e}")
