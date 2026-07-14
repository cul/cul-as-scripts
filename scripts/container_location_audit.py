import csv
import logging
import re

from asnake.utils import get_note_text

from .aspace_client import ArchivesSpaceClient
from .helpers import configure_logging

FULLY_OFFSITE = "fully off-site"
PARTIALLY_OFFSITE = "partially off-site"
FULLY_ONSITE = "fully on-site"
NOT_INDICATED = "not indicated"


_OFFSITE_RE = re.compile(r"(?:located|stored)\s+off[-\s]?site\b", re.IGNORECASE)
_ONSITE_RE = re.compile(r"(?:located|stored)\s+on[-\s]?site\b", re.IGNORECASE)

_CONTAINER_NOUN_RE = re.compile(r"(?:box(?:es)?|volumes?)\b", re.IGNORECASE)
_ENUMERATOR_DIGIT_RE = re.compile(r"\d")


def _is_enumerated(sentence):
    """Return True if a location sentence names specific containers.

    Enumeration = a container noun (box/boxes/volume/volumes) AND a digit both
    present. Runs only on sentences that already passed the location predicate,
    so a digit anywhere signals a box/volume call-out rather than the whole
    collection. Blanket forms ("This collection is located off-site", "The
    boxes are located off-site") lack the noun or the digit and return False,
    so they're treated as full rather than partial.

    Args:
        sentence (str): A sentence that has already passed the Stage 1 test.

    Returns:
        bool: True if the sentence enumerates specific containers.
    """
    return bool(
        _CONTAINER_NOUN_RE.search(sentence) and _ENUMERATOR_DIGIT_RE.search(sentence)
    )


def _split_into_sentences(text):
    """Split a single note's text into candidate sentences.

    Args:
        text (str): The `content` of one accessrestrict note_text subnote.

    Returns:
        list: Sentence strings (whitespace-stripped, empties dropped).
    """
    return [s.strip() for s in re.split(r"\.\s+", text) if s.strip()]


def classify_location(notes):
    """Classify a resource's stated location from its accessrestrict notes.

    Logic (first match wins), across all sentences that survive Stage 1:
        1. Any location sentence naming an enumerated box/volume -> partial.
        2. Else both off-site and on-site location claims present -> partial.
        3. Else only off-site claims -> fully off-site.
        4. Else only on-site claims -> fully on-site.
        5. Else no sentence asserts a physical location -> not indicated.

    Only sentences where a location verb governs a direction word (Stage 1)
    are considered; "both directions present" in rule 2 means two validated
    location claims, never a raw "onsite" substring.

    Args:
        notes (list): Text contents of the resource's accessrestrict notes,
            one string per note (already extracted from subnotes).

    Returns:
        tuple: (label, matched_sentences) where label is one of the module
            label constants and matched_sentences (list) is the location
            sentence(s) that drove the decision, for the audit column. Empty
            list when the label is NOT_INDICATED.
    """
    sentences = [sentence for note in notes for sentence in _split_into_sentences(note)]
    label = NOT_INDICATED
    matched_sentences = []
    for sentence in sentences:
        offsite_or_onsite = False
        if label != PARTIALLY_OFFSITE:
            if _OFFSITE_RE.search(sentence):
                if label == FULLY_ONSITE:
                    label = PARTIALLY_OFFSITE
                else:
                    label = FULLY_OFFSITE
                matched_sentences.append(sentence)
                offsite_or_onsite = True
            elif _ONSITE_RE.search(sentence):
                if label == FULLY_OFFSITE:
                    label = PARTIALLY_OFFSITE
                else:
                    label = FULLY_ONSITE
                matched_sentences.append(sentence)
                offsite_or_onsite = True
            if offsite_or_onsite:
                if _is_enumerated(sentence):
                    label = PARTIALLY_OFFSITE
    return label, matched_sentences


class ContainerLocationAuditor:
    """Audit RBML resources for stated location vs. observed container coverage.

    For each published resource, records what the accessrestrict notes *claim*
    about location (via the module-level `classify_location`) alongside raw
    container counts, so an archivist can judge whether the top container
    records match the notes. One CSV row per resource.
    """

    OFFSITE_LOCATION_URI = "/locations/2"

    SENTENCE_SEPARATOR = " | "

    FIELDNAMES = [
        "URI",
        "HRID",
        "Title",
        "Access Restriction Location",
        "Matched Location Sentence",
        "Total Containers",
        "Has Barcode",
        "Location No Barcode",
        "No Location No Barcode",
        "ReCAP No Barcode",
        "Container Summary",
    ]

    def __init__(self, mode="dev", repo_id=2):
        configure_logging(f"audit_container_locations_{mode}.log")
        self.as_client = ArchivesSpaceClient(mode=mode)
        self.repo_id = repo_id
        self.repo = self.as_client.aspace.repositories(repo_id)

    def _accessrestrict_texts(self, resource):
        """Extract accessrestrict note text from a resource.

        Args:
            resource (JSONModelObject): A resource record.

        Returns:
            list: Accessrestrict note content strings (may be empty).
        """
        access_notes = []
        for note in resource.notes:
            if note.json().get("type") == "accessrestrict":
                for subnote_content in get_note_text(
                    note, self.as_client.aspace.client
                ):
                    access_notes.append(subnote_content.replace("\n", " "))
        return access_notes

    def _tally_containers(self, resource):
        """Count a resource's linked top containers by physical situation.

        Args:
            resource (JSONModelObject): A resource record (uses `id_0` to query).

        Returns:
            dict: Counts keyed by field name, incl. `total`.
        """
        top_containers = self.as_client.get_top_containers_for_resource(
            self.repo, resource.id_0
        )
        container_tally = {
            "Total Containers": 0,
            "Has Barcode": 0,
            "Location No Barcode": 0,
            "No Location No Barcode": 0,
            "ReCAP No Barcode": 0,
        }
        for tc in top_containers:
            container_tally["Total Containers"] += 1
            if getattr(tc, "barcode", ""):
                container_tally["Has Barcode"] += 1
            elif tc.container_locations:
                if tc.container_locations[0].ref == self.OFFSITE_LOCATION_URI:
                    container_tally["ReCAP No Barcode"] += 1
                else:
                    container_tally["Location No Barcode"] += 1
            else:
                container_tally["No Location No Barcode"] += 1
        return container_tally

    def _extent_summary(self, resource):
        """Concatenate non-empty container_summary across the resource's extents.

        Args:
            resource (JSONModelObject): A resource record.

        Returns:
            str: Joined container_summary values.
        """
        container_summaries = []
        for extent in resource.extents:
            if extent.json().get("container_summary"):
                container_summaries.append(extent.json().get("container_summary"))
        return self.SENTENCE_SEPARATOR.join(container_summaries)

    def _audit_resource(self, resource):
        """Assemble one CSV row for a single resource.

        Args:
            resource (JSONModelObject): A resource record.

        Returns:
            dict: One row keyed by FIELDNAMES.
        """
        label, matched_sentences = classify_location(
            self._accessrestrict_texts(resource)
        )
        tally = self._tally_containers(resource)
        return {
            "URI": resource.uri,
            "HRID": resource.id_0,
            "Title": resource.title,
            "Access Restriction Location": label,
            "Matched Location Sentence": self.SENTENCE_SEPARATOR.join(
                matched_sentences
            ),
            "Container Summary": self._extent_summary(resource),
            **tally,
        }

    def run(self, output_path):
        """Audit all published resources and write one CSV row each.

        Args:
            output_path (str or Path): Destination CSV path.
        """
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
            writer.writeheader()
            for resource in self.as_client.published_resources(self.repo_id):
                try:
                    writer.writerow(self._audit_resource(resource))
                except Exception as e:
                    logging.exception(f"Failed on {getattr(resource, 'uri', '?')}: {e}")
