import csv
import logging
import re


def configure_logging(filename):
    """Configure logging to write to both a file and stdout.

    Args:
        filename (str): Path to the log file
    """
    logging.basicConfig(
        datefmt="%m/%d/%Y %I:%M:%S %p",
        format="%(asctime)s %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler(filename),
            logging.StreamHandler(),
        ],
    )


def write_data_to_csv(sheet_data, filepath):
    """Write data to a CSV file.

    Args:
        sheet_data (list): list of lists (rows)
        filepath (Path obj or str): Path object or string of CSV filepath
    """
    with open(filepath, "w") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(sheet_data)


def construct_multipart_note(note_type, note_text, publish=True):
    """Build an ArchivesSpace multipart note dict.

    Args:
        note_type (str): ASpace note type (e.g., "accessrestrict", "scopecontent")
        note_text (str): Text content of the note
        publish (bool): Whether the note should be published. Defaults to True.

    Returns:
        dict: ASpace note_multipart JSON object
    """
    note = {
        "jsonmodel_type": "note_multipart",
        "type": note_type,
        "subnotes": [
            {
                "jsonmodel_type": "note_text",
                "content": note_text,
                "publish": publish,
            }
        ],
        "publish": publish,
    }
    return note


def construct_instance_with_container(container_uri):
    """Build an ArchivesSpace box instance dict linked to a top container.

    Args:
        container_uri (str): URI of the top container to link

    Returns:
        dict: ASpace instance JSON object
    """
    return {
        "instance_type": "box",
        "jsonmodel_type": "instance",
        "is_representative": False,
        "sub_container": {
            "jsonmodel_type": "sub_container",
            "top_container": {"ref": container_uri},
        },
    }


def construct_digital_instance(digital_object_uri):
    """Build an ArchivesSpace digital object instance dict.

    Args:
        digital_object_uri (str): URI of the digital object to link

    Returns:
        dict: ASpace instance JSON object
    """
    return {
        "instance_type": "digital_object",
        "jsonmodel_type": "instance",
        "is_representative": False,
        "digital_object": {"ref": digital_object_uri},
    }


def construct_external_doc(title, location, publish=False):
    """Build an ArchivesSpace external document dict.

    Args:
        title (str): Title of the external document
        location (str): URL or path to the external document
        publish (bool): Whether the document should be published. Defaults to False.

    Returns:
        dict: ASpace external_document JSON object
    """
    return {
        "title": title,
        "location": location,
        "publish": publish,
        "jsonmodel_type": "external_document",
    }


def construct_rbml_location(
    floor, aisle, section, shelf, location_profile="/location_profiles/31"
):
    """Build an ArchivesSpace location dict for an RBML shelf.

    Args:
           floor (str): The floor coordinate (e.g., "Stack 14")
           aisle (str): The aisle coordinate (e.g., "3e")
           section (str): The section coordinate (e.g., "6")
           shelf (str): The shelf coordinate (e.g., "2")
           location_profile (str): URI of the location profile

    Returns:
        dict: ASpace location JSON object
    """
    return {
        "jsonmodel_type": "location",
        "building": "Butler",
        "floor": floor,
        "coordinate_1_label": "Aisle",
        "coordinate_1_indicator": aisle,
        "coordinate_2_label": "Section",
        "coordinate_2_indicator": section,
        "coordinate_3_label": "Shelf",
        "coordinate_3_indicator": shelf,
        "location_profile": {"ref": location_profile},
        "owner_repo": {"ref": "/repositories/2"},
    }


def construct_rbml_mapcase_location(
    floor, mapcase, drawer, location_profile="/location_profiles/29"
):
    """Build an ArchivesSpace location dict for an RBML mapcase.

    Args:
           floor (str): The floor coordinate (e.g., "Stack 14")
           mapcase (str): The mapcase coordinate (e.g., "A")
           drawer (str): The drawer coordinate (e.g., "1")
           location_profile (str): URI of the location profile

    Returns:
        dict: ASpace location JSON object
    """
    return {
        "jsonmodel_type": "location",
        "building": "Butler",
        "floor": floor,
        "coordinate_1_label": "Mapcase",
        "coordinate_1_indicator": mapcase,
        "coordinate_2_label": "Drawer",
        "coordinate_2_indicator": drawer,
        "location_profile": {"ref": location_profile},
        "owner_repo": {"ref": "/repositories/2"},
    }


def has_note_type(ao, note_type="physdesc"):
    """Check whether an archival object has a note of a given type.

    Args:
        ao (obj): ASnake archival object
        note_type (str): Note type to check for. Defaults to "physdesc".

    Returns:
        bool: True if a note of the given type exists, False otherwise
    """
    if not getattr(ao, "notes", None):
        return False
    return bool([x for x in ao.notes if x.type == note_type])


def create_date_object(date_string):
    """Turns a date string into an ASpace date.

    Args:
        date_string (str): date formatted YYYY, YYYY-DD, YYYY-MM-DD, or YYYY-YYYY

    Returns:
        dict: ASpace date object
    """
    date_object = {"label": "creation", "jsonmodel_type": "date"}
    single_date_formats = [r"\d\d\d\d", r"\d\d\d\d-\d\d", r"\d\d\d\d-\d\d-\d\d"]
    if any(re.fullmatch(x, date_string) for x in single_date_formats):
        date_object["begin"] = date_string
        date_object["date_type"] = "single"
        return date_object
    elif re.fullmatch(r"\d\d\d\d-\d\d\d\d", date_string):
        date_object["begin"] = date_string.split("-")[0]
        date_object["end"] = date_string.split("-")[-1]
        date_object["date_type"] = "inclusive"
        return date_object
    else:
        raise ValueError(f"Unrecognized date format: {date_string!r}")


def has_one_series(children):
    """Check whether a resource has exactly one series with children.

    Args:
        children (list): List of child nodes from an ASpace tree waypoint response

    Returns:
        bool: True if there is exactly one child and it has children of its own,
            False otherwise
    """
    return len(children) == 1 and children[0]["child_count"] > 0


def collection_matches_series(collection_title, series_title):
    """Check whether a collection title matches a series title.

    Accounts for common series title prefixes like "I. " and "I: ".

    Args:
        collection_title (str): Title of the collection
        series_title (str): Title of the series

    Returns:
        bool: True if the titles match, False otherwise
    """
    parsed_series = [
        series_title,
        series_title.split("I. ")[-1],
        series_title.split("I: ")[-1],
    ]
    if collection_title in parsed_series:
        return True


def box_number_parser(box_numbers):
    """Parse box numbers from a location spreadsheet.

    Args:
        box_numbers (str): Value of Box/Volume Numbers column

    Returns:
        list[str]: box numbers
    """
    if not box_numbers.lower().startswith("box"):
        raise Exception(f"{box_numbers} does not describe boxes")
    box_num_list = re.split(r"[;,&]", box_numbers)
    return box_num_list
    # TODO: remove items in list that do not contain an integer
