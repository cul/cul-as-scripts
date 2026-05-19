import logging

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging


class MetadataRights:
    """Add metadata rights declarations to all eligible published resources.

    Args:
        repo_id (int): ASpace repository ID
        rights (str): Rights declaration key from RIGHTS_MAPPING. Defaults to "CC0".
    """

    RIGHTS_MAPPING = {
        "CC0": {
            "file_uri": "https://creativecommons.org/publicdomain/zero/1.0/",
            "license": "public_domain",
            "jsonmodel_type": "metadata_rights_declaration",
        }
    }

    def __init__(self, mode="test"):
        configure_logging(f"metadata_rights_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)

    def run(self, repo_id, rights="CC0"):
        """Determine whether a resource should receive a metadata rights declaration.

        Args:
            resource (obj): ASnake resource record

        Returns:
            bool: True if the resource should be updated, False otherwise
        """
        for resource in self.as_client.published_resources(repo_id):
            if not self.should_update_resource(resource):
                continue
            try:
                resource_json = resource.json()
                self.as_client.update_aspace_field(
                    resource_json,
                    "metadata_rights_declarations",
                    [self.RIGHTS_MAPPING[rights]],
                )
                logging.info(f"Added metadata rights declaration to {resource.uri}")
            except Exception as e:
                logging.error(f"Failed to update {resource.uri}: {e}")

    def should_update_resource(self, resource):
        if resource.title.startswith("Carnegie Corporation of New York"):
            return False
        return not resource.metadata_rights_declarations
