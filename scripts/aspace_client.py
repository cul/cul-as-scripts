from configparser import ConfigParser
from uuid import uuid4

from asnake.aspace import ASpace
from asnake.utils import get_note_text


class ArchivesSpaceClient:
    """Handles communication with ArchivesSpace."""

    RBML_REPO_ID = 2
    RBML_BUILDING = "Butler"
    RBML_LOCATION_PROFILE = "/location_profiles/31"

    def __init__(self, mode="dev"):
        self.config = ConfigParser()
        self.config.read("local_settings.cfg")
        self.aspace = ASpace(
            baseurl=self.config.get("ArchivesSpace", f"{mode}_baseurl"),
            username=self.config.get("ArchivesSpace", "username"),
            password=self.config.get("ArchivesSpace", "password"),
        )

    def get_digital_objects(self, repo_id):
        """Get data about digital object records from AS.

        Args:
            repo_id (int): ASpace repository ID (e.g., 2)

        Yields:
          dict: Full JSON of AS digital object record
        """
        repo = self.aspace.repositories(repo_id)
        search_query = "primary_type:digital_object"
        for digital_object in repo.search.with_params(q=search_query):
            digital_object_json = digital_object.json()
            yield digital_object_json

    def delete_in_aspace(self, target):
        """Delete a thing in AS.

        Args:
            target (str): URI of thing to delete
        """
        self.aspace.client.delete(target)

    def get_ead(self, repo_id, resource_id):
        """Get EAD for a resource.

        Args:
            repo_id (int): ASpace repository ID (e.g., 2)
            resource_id (int): ASpace resource ID (e.g., 1234)

        Returns:
            str: XML response
        """
        params = {"include_unpublished": False, "include_daos": True}
        response = self.aspace.client.get(
            f"/repositories/{repo_id}/resource_descriptions/{resource_id}.xml",
            params=params,
        )
        return response.content.decode("utf-8")

    def get_json(self, uri):
        """Get JSON of an ASpace record.

        Args:
            uri (str): ASpace uri

        Returns:
            dict: JSON response of the ASpace record
        """
        response = self.aspace.client.get(uri)
        return response.json()

    def published_resources(self, repo_id):
        """Get all published, unsuppressed resources in a repository.

        Args:
            repo_id (int): ASpace repository ID (e.g., 2)

        Yields:
            ASnakeObject: Published, unsuppressed resource records
        """
        for resource in self.aspace.repositories(repo_id).resources:
            if resource.publish and not resource.suppressed:
                yield resource

    def published_repositories(self):
        """Get all published repositories in the ASpace instance.

        Yields:
            ASnakeObject: Published repository records
        """
        for repo in self.aspace.repositories:
            if repo.publish:
                yield repo

    def update_aspace_field(self, aspace_json, field_name, new_info):
        """Updates (or adds) a field to an ArchivesSpace record.

        Args:
            aspace_json (dict): ArchivesSpace data
            field_name (str): name of field to update
            new_info (str): value of updated field
        """
        aspace_json[field_name] = new_info
        self.aspace.client.post(aspace_json["uri"], json=aspace_json)

    def get_ao_by_ref_id(self, repo_id, ref_id):
        """Get an archival object by its Ref ID

        Args:
            repo_id (int): ASpace repository ID (e.g., 2)
            ref_id (str): Ref ID of the archival object

        Returns:
            dict: JSON of the archival object record

        Raises:
            ValueError: If no archival object is found for the given ref_id
        """
        results = (
            self.aspace.client.get(
                f"/repositories/{repo_id}/find_by_id/archival_objects?ref_id[]={ref_id}"
            )
            .json()
            .get("archival_objects", [])
        )
        if not results:
            raise ValueError(f"No results found for refid {ref_id}")
        return results[0]["_resolved"]

    def get_all_aos_in_resource(self, resource_id, repo_id=None):
        """Get all archival objects in a resource.

        Args:
            resource_id (int): ASpace resource ID (e.g., 1234)
            repo_id (int, optional): ASpace repository ID. Defaults to RBML_REPO_ID.

        Yields:
            ASnakeObject: Archival object records in the resource
        """
        repo_id = repo_id or self.RBML_REPO_ID
        search_query = f'primary_type:archival_object resource:"/repositories/{repo_id}/resources/{resource_id}"'
        search_results = self.aspace.repositories(repo_id).search.with_params(
            q=search_query
        )
        for ao in search_results:
            yield ao

    def get_all_dos_in_resource(self, resource_id, repo_id=None):
        """Get all digital objects in a resource.

        Args:
            resource_id (int): ASpace resource ID (e.g., 1234)
            repo_id (int, optional): ASpace repository ID. Defaults to RBML_REPO_ID.

        Yields:
            ASnakeObject: Digital object records in the resource
        """
        repo_id = repo_id or self.RBML_REPO_ID
        search_query = f'primary_type:digital_object collection_uri_u_sstr:"/repositories/{repo_id}/resources/{resource_id}"'
        search_results = self.aspace.repositories(repo_id).search.with_params(
            q=search_query
        )
        for do in search_results:
            yield do

    def get_note_content_by_type(self, ao_or_resource, note_type):
        """Get the text of notes of a given type in an archival object or resource record.

        Args:
            ao_or_resource (obj): ASnake archival object or resource record
            note_type (str): Note type to filter by (e.g., "accessrestrict")

        Returns:
            str: Note text joined by "; " if multiple notes of the given type exist,
            or an empty string if none are found

        """
        notes = [
            " ".join(get_note_text(x, self.aspace.client)).replace("\n", " ")
            for x in ao_or_resource.notes
            if x.json().get("type") == note_type
        ]
        return "; ".join(notes)

    def create_top_container(self, repo_id, indicator, type="box"):
        """Creates a new top container record in ASpace.

        Args:
            repo_id (int): ASpace repository ID (e.g., 2)
            indicator (int or str): Box number or label for the container

        Returns:
            str: URI of the newly created top container
        """
        data = {
            "jsonmodel_type": "top_container",
            "indicator": indicator,
            "type": type,
        }
        response = self.aspace.client.post(
            f"/repositories/{repo_id}/top_containers", json=data
        )
        return response.json()["uri"]

    def create_top_containers_range(self, repo_id, start, end):
        """Create a range of sequentially numbered top container (box) records.

        Args:
            repo_id (int): ASpace repository ID (e.g., 2)
            start (int): First box number in the range (inclusive)
            end (int): Last box number in the range (inclusive)

        Returns:
            dict: Mapping of box number strings to their ASpace URIs
                e.g. {"1": "/repositories/2/top_containers/1"}
        """
        boxes = {}
        for box_num in range(start, end + 1):
            box_uri = self.create_top_container(repo_id, box_num)
            boxes[str(box_num)] = box_uri
        return boxes

    def get_top_containers_for_resource(self, repo, resource_identifier):
        """Get all top containers associated with a resource.

        Args:
            repo (obj): ASnake repository object
            resource_identifier (str): Collection identifier to search by

        Yields:
            ASnakeObject: Top container records linked to the resource
        """
        search_query = f"primary_type:top_container collection_identifier_stored_u_sstr:{resource_identifier}"
        search_results = repo.search.with_params(q=search_query)
        for top_container in search_results:
            yield top_container

    def create_digital_object(self, repo_id, title, url):
        """Create a new digital object record in ASpace.

        Args:
            repo_id (int): ASpace repository ID (e.g., 2)
            title (str): Title of the digital object
            url (str): File URI for the digital object's representative file version

        Returns:
            str: URI of the newly created digital object
        """
        data = {
            "jsonmodel_type": "digital_object",
            "title": title,
            "digital_object_id": str(uuid4()).replace("-", ""),
            "publish": True,
            "file_versions": [
                {
                    "file_uri": url,
                    "publish": True,
                    "jsonmodel_type": "file_version",
                    "is_representative": False,
                }
            ],
        }
        response = self.aspace.client.post(
            f"/repositories/{repo_id}/digital_objects", json=data
        )
        uri = response.json()["uri"]
        return uri

    def get_orphan_digital_objects(self, repo_id):
        """Get digital objects that do not have linked instances.

        Returns:
            list[str]: URIs of digital objects with no linked instances
        """
        orphan_daos = [
            dao["uri"]
            for dao in self.get_digital_objects(repo_id)
            if not dao.get("linked_instances")
        ]
        return orphan_daos

    def create_rbml_location(self, floor, aisle, section, shelf):
        """Creates a new ArchivesSpace location record.

        Constructs the location JSON payload and posts it to the ArchivesSpace API.

        Args:
            floor (str): The value of the floor field (e.g., "Stack 14").
            aisle (str): The coordinate for Aisle.
            section (str): The coordinate for Section.
            shelf (str): The coordinate for Shelf.

        Returns:
            str: The URI of the newly created ArchivesSpace location.
        """
        location_json = {
            "jsonmodel_type": "location",
            "building": self.RBML_BUILDING,
            "floor": floor,
            "coordinate_1_label": "Aisle",
            "coordinate_1_indicator": aisle,
            "coordinate_2_label": "Section",
            "coordinate_2_indicator": section,
            "coordinate_3_label": "Shelf",
            "coordinate_3_indicator": shelf,
            "location_profile": {"ref": self.RBML_LOCATION_PROFILE},
            "owner_repo": {"ref": f"/repositories/{self.RBML_REPO_ID}"},
        }
        response = self.aspace.client.post("/locations", json=location_json)
        response.raise_for_status()
        return response.json()["uri"]

    def get_rbml_location(self, floor, aisle, section, shelf):
        """Find an existing RBML location record by its coordinates.

        Args:
            floor (str): Floor value (e.g., "Stack 14")
            aisle (str): Aisle coordinate
            section (str): Section coordinate
            shelf (str): Shelf coordinate

        Returns:
            str: URI of the matching location record

        Raises:
            Exception: If the number of matching results is not exactly 1
        """
        coordinates = f"Aisle: {aisle}, Section: {section}, Shelf: {shelf}"
        search_query = f'owner_repo_display_string_u_ssort:RBML building:{self.RBML_BUILDING} floor:"{floor}" "{coordinates}"'
        response = self.aspace.repositories(self.RBML_REPO_ID).search.with_params(
            q=search_query
        )
        results = [x for x in response]
        if len(results) == 1:
            return results[0].uri
        else:
            raise Exception(
                f"{len(results)} results found for {floor}, {aisle}, {section}, {shelf}"
            )

    def add_location_to_top_container(
        self, top_container_uri, location_uri, start_date="2020-01-01"
    ):
        """Attach a location to a top container record.

        Args:
            top_container_uri (str): URI of the top container to update
            location_uri (str): URI of the location to attach
            start_date (str): Start date for the container location in YYYY-MM-DD
                format. Defaults to "2020-01-01".

        Raises:
            Exception: If the top container already has attached locations
        """
        top_container_json = self.get_json(top_container_uri)
        if top_container_json.get("container_locations"):
            raise Exception(f"{top_container_uri} already has attached locations")
        container_locations = [
            {
                "jsonmodel_type": "container_location",
                "status": "current",
                "start_date": start_date,
                "ref": location_uri,
            }
        ]
        self.update_aspace_field(
            top_container_json, "container_locations", container_locations
        )

    def move_to_new_parent(self, new_parent_id, position, ao_uri):
        """Moves an Archival Object to a new parent Archival Object in ArchivesSpace.

        Args:
            new_parent_id (int): The ArchivesSpace ID of the new parent AO (series)
            position (int): Position among siblings under the new parent
            ao_uri (str): URI of the archival object to mov
        """
        params = {"parent": new_parent_id, "position": position}
        response = self.aspace.client.post(f"{ao_uri}/parent", params=params)
        response.raise_for_status()

    def get_series_count(self, resource_uri):
        """Get the count of immediate children of a resource"""
        children = self.aspace.client.get(
            f"{resource_uri}/tree/waypoint?offset=0"
        ).json()
        return len(children)

    def get_call_num(self, resource):
        """Get the local call number for a resource.

        Args:
            resource (obj): ASnake resource record

        Returns:
            str: Local call number if present, empty string if not found
        """
        try:
            call_num = resource.user_defined.string_1
        except AttributeError:
            call_num = ""
        return call_num

    def update_all_aos_in_resource(self, resource_id, repo_id=None):
        """Re-post every archival object in a resource.

        Args:
            resource_id (int): ASpace resource ID (e.g., 1234)
            repo_id (int, optional): ASpace repository ID. Defaults to RBML_REPO_ID.
        """
        repo_id = repo_id or self.RBML_REPO_ID
        for ao in self.get_all_aos_in_resource(resource_id, repo_id):
            response = self.aspace.client.post(ao.uri, json=ao.json())
            response.raise_for_status()

    def strip_parens_from_content(self, ao_json):
        """Strip surrounding parentheses from subnote content in an archival object.

        Args:
            ao_json (dict): ArchivesSpace archival object JSON

        Note:
            TODO: handle single-part notes (notes without subnotes)
        """
        notes = ao_json["notes"]
        for x in notes:
            if x.get("subnotes"):
                x["subnotes"][0]["content"] = x["subnotes"][0]["content"].strip("()")
        self.update_aspace_field(ao_json, "notes", notes)

    def get_resource_children(self, resource_uri):
        """Get the immediate children of a resource from its tree waypoint.

        Args:
            resource_uri (str): URI of the resource

        Returns:
            list: Child node dicts from the first tree waypoint
        """
        children = self.aspace.client.get(
            f"{resource_uri}/tree/waypoint?offset=0"
        ).json()
        return children

    def add_child_to_resource(self, resource_uri, ao_uri, position):
        """Move an archival object to be a direct child of a resource.

        Args:
            resource_uri (str): URI of the resource
            ao_uri (str): URI of the archival object to move
            position (int): Position among the resource's direct children
        """
        params = {
            "children[]": ao_uri,
            "position": position,
        }
        response = self.aspace.client.post(
            f"{resource_uri}/accept_children", params=params
        )
        response.raise_for_status()

    def get_resource_by_hrid(self, repo, hrid):
        """Finds the resource whose id_0 matches a FOLIO HRID.

        Args:
            repo (obj): ASnake repository object to search within.
            hrid (str): FOLIO instance HRID, which corresponds to the resource's
                id_0.

        Returns:
            obj: The matching ASnake resource object, or None if no resource has
                an id_0 equal to the HRID.
        """
        resources = repo.search.with_params(
            q=f"primary_type:resource identifier:{hrid}"
        )
        for resource in resources:
            if resource.id_0 == hrid:
                return resource
        return None
