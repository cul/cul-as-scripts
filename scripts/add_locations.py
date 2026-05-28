import logging
from pathlib import Path

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging, construct_rbml_location


class AddLocations:
    def __init__(self, mode="dev", repo_id=2):
        configure_logging(f"add_locations_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)
        self.repo = self.as_client.aspace.repositories(repo_id)

    def create_locations_from_textfile(self, input_file):
        """Create RBML location records from a plain text file.

        Each line in the file should contain a comma-separated location string
        in the format: stack, aisle, section, shelf (e.g., "14, 22e, 01, 01").
        Skips locations that already exist in ASpace. Logs errors without
        stopping execution.

        Args:
            input_file (str or Path): Path to the text file of location strings
        """
        file_path = Path(input_file)
        for line in file_path.read_text().splitlines():
            try:
                stack_num, aisle, section, shelf = [
                    x.strip().lstrip("0") for x in line.split(",")
                ]
                if self.get_location(f"Stack {stack_num}", aisle, section, shelf):
                    continue
                location_json = construct_rbml_location(
                    f"Stack {stack_num}", aisle, section, shelf
                )
                response = self.as_client.aspace.client.post(
                    "/locations", json=location_json
                )
                response.raise_for_status()
                logging.info(
                    f"Created location: Stack {stack_num}, {aisle}, {section}, {shelf}"
                )
            except Exception as e:
                logging.error(e)

    def get_location(self, floor, aisle, section, shelf):
        """Search for an existing RBML location record by its coordinates.

        Args:
            floor (str): Floor value (e.g., "Stack 14")
            aisle (str): Aisle coordinate (e.g., "22e")
            section (str): Section coordinate (e.g., "6")
            shelf (str): Shelf coordinate (e.g., "2")

        Returns:
            str: URI of the matching location if exactly one result is found
            bool: False if no results are found

        Raises:
            Exception: If more than one matching location is found
        """
        coordinates = f"Aisle: {aisle}, Section: {section}, Shelf: {shelf}"
        search_query = f'owner_repo_display_string_u_ssort:RBML building:Butler floor:"{floor}" "{coordinates}"'
        response = self.repo.search.with_params(q=search_query)
        results = [x for x in response]
        if len(results) == 1:
            return results[0].uri
        elif not results:
            return False
        elif len(results) > 1:
            raise Exception(
                f"More than one result found for {floor}, {aisle}, {section}, {shelf}"
            )
