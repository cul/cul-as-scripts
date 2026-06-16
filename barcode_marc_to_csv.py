"""Converts a FOLIO Data Export .mrc file to a CSV with one row per item (box).

Each row carries the instance HRID and title, the item's parent holdings
record (HRID, call number, location), and the item's enumeration (box label),
barcode, and HRID.

This converter expects the FOLIO Data Export profile that emits:
    - 901 $a: Instance HRID
    - 902 $a: Resource title
    - 911:    Holdings record -- $a holdings HRID, $b location
              (display name with code in parens), $c call number
    - 921:    Item record -- $e enumeration (box label), $p barcode,
              $h item HRID, $3 parent holdings HRID, $c item call number,
              $a item label/type (e.g. "1 Box", "Printed Matter")

Items are joined to their holdings by a real foreign key: each item's 921 $3
holds the HRID of its parent holdings record, which matches a 911 $a. This is
an exact lookup -- there is NO positional/ordering assumption, so two holdings
that share a location and call number (e.g. a processed and an [Unprocessed]
run under one instance) cannot be flipped.

Usage:
    python barcode_marc_to_csv.py input.mrc [output.csv]

If output.csv is not specified, the output file is named after the input file
with a .csv extension.
"""

import csv
import re
import sys
from pathlib import Path

from pymarc import MARCReader

# Pulls the code out of a FOLIO location display string, e.g.
# "Rare Manuscripts Offsite (off,rbms)" -> ("Rare Manuscripts Offsite", "off,rbms")
LOCATION_CODE = re.compile(r"^(.*?)\s*\(([^)]+)\)\s*$")


def split_location(location):
    """Split a FOLIO location display string into name and code.

    Args:
        location (str): Location string, typically "Name (code)".

    Returns:
        tuple[str, str]: (location_name, location_code). If no parenthetical
            code is present, location_code is "" and location_name is the
            whole input.
    """
    match = LOCATION_CODE.match(location or "")
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return (location or "").strip(), ""


def build_holdings_index(record):
    """Map each holdings HRID in a record to its holdings fields.

    Args:
        record (pymarc.Record): A single MARC record.

    Returns:
        dict[str, dict]: holdings HRID -> {call_number, location_name,
            location_code} for every 911 field in the record.
    """
    holdings_index = {}
    for field in record.get_fields("911"):
        holdings_hrid = field.get("a", "")
        location_name, location_code = split_location(field.get("b", ""))
        holdings_index[holdings_hrid] = {
            "call_number": field.get("c", ""),
            "location_name": location_name,
            "location_code": location_code,
        }
    return holdings_index


def parse_marc(path):
    """Parse a MARC21 file into a list of item rows.

    Args:
        path (str): Path to the MARC21 .mrc file to parse.

    Returns:
        list[dict]: One dict per item (921 field), with keys: instance_hrid,
        title, holdings_hrid, call_number, location_name, location_code,
        item_enumeration, item_barcode, and item_hrid.

    Raises:
        ValueError: If an item's parent holdings HRID (921 $3) does not match
            any holdings record (911 $a) in the same instance. This is the only
            remaining join failure mode and is surfaced loudly rather than
            written out as a blank holding.
    """
    rows = []
    with open(path, "rb") as f:
        reader = MARCReader(f)
        for record in reader:
            instance_hrid = record["901"]["a"] if record["901"] else ""
            title = record["902"]["a"] if record["902"] else ""
            holdings_index = build_holdings_index(record)

            for item in record.get_fields("921"):
                holdings_hrid = item.get("3", "")
                if holdings_hrid not in holdings_index:
                    raise ValueError(
                        f"Instance {instance_hrid}: item {item.get('h', '')} "
                        f"points at holdings HRID {holdings_hrid!r}, which is "
                        f"not among this record's holdings "
                        f"({sorted(holdings_index)})."
                    )
                holdings = holdings_index[holdings_hrid]
                rows.append(
                    {
                        "instance_hrid": instance_hrid,
                        "title": title,
                        "holdings_hrid": holdings_hrid,
                        "call_number": holdings["call_number"],
                        "location_name": holdings["location_name"],
                        "location_code": holdings["location_code"],
                        "item_enumeration": item.get("e", ""),
                        "item_barcode": item.get("p", ""),
                        "item_hrid": item.get("h", ""),
                    }
                )
    return rows


def write_csv(rows, output_path):
    """Write item rows to a CSV file.

    Args:
        rows (list[dict]): Rows as returned by parse_marc().
        output_path (str): Path to the CSV file to write (created/overwritten).
    """
    fieldnames = [
        "instance_hrid",
        "title",
        "holdings_hrid",
        "call_number",
        "location_name",
        "location_code",
        "item_enumeration",
        "item_barcode",
        "item_hrid",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    """Parse command-line arguments and run the MARC-to-CSV conversion.

    Raises:
        SystemExit: If no input file argument is provided.
    """
    if len(sys.argv) < 2:
        print("Usage: python barcode_marc_to_csv.py input.mrc [output.csv]")
        sys.exit(1)

    input_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        output_path = str(Path(input_path).with_suffix(".csv"))

    print(f"Parsing {input_path} ...")
    rows = parse_marc(input_path)
    print(f"Writing {len(rows)} rows to {output_path} ...")
    write_csv(rows, output_path)
    print("Done.")


if __name__ == "__main__":
    main()
