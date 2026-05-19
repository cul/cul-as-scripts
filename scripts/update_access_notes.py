import logging

from asnake.utils import walk_tree

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging, construct_multipart_note


class AccessUpdater:
    """Updates access restriction notes in ArchivesSpace archival objects and resources."""

    def __init__(self, mode="dev"):
        configure_logging(f"access_updater_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)

    def run_series(self, series_uri, new_text, text_to_replace=None):
        """Update access restriction notes in all AOs under a series.

        If text_to_replace is provided, replaces matching note content. Otherwise,
        adds a new access restriction note to AOs that have no notes.

        Args:
            series_uri (str): URI of the series archival object
            new_text (str): New note text to add or substitute
            text_to_replace (str, optional): Existing note text to replace.
                If None, adds new notes to AOs with no notes.
        """
        children = walk_tree(series_uri, self.as_client.aspace.client)
        next(children)
        for ao_json in children:
            update = False
            if text_to_replace:
                notes = ao_json["notes"]
                for note in reversed(notes):
                    if note.get("type") == "accessrestrict":
                        for subnote in note.get("subnotes", []):
                            content = subnote["content"]
                            if text_to_replace in content:
                                update = True
                                subnote["content"] = content.replace(
                                    text_to_replace, new_text
                                )
            elif len(ao_json["notes"]) == 0:
                new_note = construct_multipart_note("accessrestrict", new_text)
                ao_json["notes"].append(new_note)
                update = True
            if update:
                self.as_client.aspace.client.post(ao_json["uri"], json=ao_json)
                logging.info(f"Updated {ao_json['display_string']}")
            else:
                logging.info(f"Did not update {ao_json['display_string']}")

    def update_resources_in_repo(self, repo_id, notes_to_replace, new_text):
        """Replace matching access restriction note content across all published resources.

        Args:
            repo_id (int): ASpace repository ID
            notes_to_replace (list[str]): List of note content strings to replace
            new_text (str): Replacement note text
        """
        for resource in self.as_client.published_resources(repo_id):
            update = False
            resource_json = resource.json()
            notes = resource_json["notes"]
            for note in reversed(notes):
                if note.get("type") == "accessrestrict":
                    for subnote in note.get("subnotes", []):
                        content = subnote["content"]
                        if content in notes_to_replace:
                            update = True
                            subnote["content"] = new_text
            if update:
                self.as_client.aspace.client.post(resource.uri, json=resource_json)
                logging.info(f"Updated {resource.title} ({resource.uri})")
