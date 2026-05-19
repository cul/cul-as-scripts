from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging


class AddLocations:
    def __init__(self, mode="dev", repo_id=2):
        configure_logging(f"add_locations_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)
        self.repo = self.as_client.aspace.repositories(repo_id)
