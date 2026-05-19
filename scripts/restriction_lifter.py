import logging
from datetime import date

from asnake.utils import get_note_text

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging, write_data_to_csv


class GetAccessNotes:
    """Finds and manages access restriction notes in ArchivesSpace.

    Provides methods to export flagged access restriction notes to a CSV
    and to remove restrictions that have expired in a given year.
    """

    def __init__(self, mode="dev"):
        configure_logging(f"get_access_notes_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)
        self.repo = self.as_client.aspace.repositories(self.as_client.RBML_REPO_ID)

    def create_csv(self, year):
        """Export access restriction notes expiring in a given year to a CSV.

        Args:
            year (int): Year to search for in access restriction note text
        """
        rows = []
        rows.append(
            [
                "id_0",
                "Collection Title",
                "Component Display String",
                "Component URI",
                "Note ID",
                "Note Text",
            ]
        )
        for ao, flagged_notes in self._get_flagged_notes(year):
            rows.append(
                [
                    ao.resource.id,
                    ao.resource.title,
                    ao.display_string,
                    ao.uri,
                    flagged_notes[0].persistent_id,
                    get_note_text(flagged_notes[0], self.as_client)[0],
                ]
            )
        write_data_to_csv(rows, f"accessrestrict_{year}_{self.repo.name}.csv")

    def remove_restrictions(self, year):
        """Remove access restriction notes expiring in a given year.

        Deletes flagged notes from their archival objects and appends a
        revision statement to each affected resource.

        Args:
            year (int): Year to search for in access restriction note text
        """
        updated_resources = []
        revision_statement = self.revision_statement(year)
        for ao, flagged_notes in self._get_flagged_notes(year):
            notes = ao.json()["notes"]
            matching_note = [
                x for x in notes if x["persistent_id"] == flagged_notes[0].persistent_id
            ]
            if matching_note:
                notes.remove(matching_note[0])
                self.as_client.update_aspace_field(ao.json(), "notes", notes)
                logging.info(f"Updated archival object {ao.ref_id}")
                if ao.resource.uri not in updated_resources:
                    updated_resources.append(ao.resource.uri)
                    logging.info(f"Updated components in {ao.resource.title}")
        for resource_uri in updated_resources:
            resource_json = self.as_client.aspace.client.get(resource_uri).json()
            revision_statements = resource_json.get("revision_statements", [])
            revision_statements.append(revision_statement)
            self.as_client.update_aspace_field(
                resource_json, "revision_statements", revision_statements
            )
            logging.info(f"Added revision statement to {resource_json['title']}")

    def _get_flagged_notes(self, year):
        """Search for archival objects with access restriction notes containing a given year.

        Args:
            year (int): Year to search for in access restriction note text

        Yields:
            tuple[ASnakeObject, list]: (archival object, list of matching notes)
        """
        search_query = f"primary_type:archival_object notes_published:{year}"
        for ao in self.repo.search.with_params(q=search_query):
            access_notes = [x for x in ao.notes if x.type == "accessrestrict"]
            flagged = [
                x
                for x in access_notes
                if str(year) in get_note_text(x, self.as_client.aspace.client)[0]
            ]
            if flagged:
                yield ao, flagged

    def revision_statement(self, year):
        """Build a revision statement dict for restrictions lifted in a given year.

        Args:
            year (int): Year restrictions were lifted

        Returns:
            dict: ASpace revision_statement JSON object with today's date
        """
        today = date.today()
        return {
            "date": today.strftime("%Y-%m-%d"),
            "description": f"Restrictions expiring in {year} have been lifted.",
            "publish": True,
            "jsonmodel_type": "revision_statement",
        }
