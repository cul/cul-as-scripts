"""Converts a FOLIO Data Export .mrc file to a CSV with one row per item (box).

Each row includes the instance HRID, title, holdings call number and location,
and the item's enumeration (box label), barcode, and HRID.

Usage:
    python marc_to_csv.py input.mrc [output.csv]

If output.csv is not specified, the output file will be named after the input
file with a .csv extension.
"""

import csv
import sys
from pathlib import Path

from pymarc import MARCReader


def parse_marc(path):
    """Parses a MARC21 file and returns a list of row dicts, one per item.

    Each record is expected to follow the FOLIO Data Export format with:
        - 001: Instance HRID (control field)
        - 245 $a: Resource title
        - 988: Holdings data ($a call number, $b location name, $c location code)
        - 989: Item data ($h enumeration, $i barcode, $0 item HRID)

    Records with multiple 988 holdings fields will have their call numbers,
    location names, and location codes pipe-separated in the output, since the
    export does not include a direct link between individual 989 item fields and
    their parent 988 holdings field.

    Args:
        path (str): Path to the MARC21 .mrc file to parse.

    Returns:
        list[dict]: A list of dicts, each representing one item (box), with
        keys: instance_hrid, title, call_number, location_name, location_code,
        item_enumeration, item_barcode, and item_hrid.
    """
    rows = []

    with open(path, "rb") as f:
        reader = MARCReader(f)
        for record in reader:
            instance_hrid = record["001"].value() if record["001"] else ""
            instance_title = record["245"]["a"].rstrip(" /") if record["245"] else ""

            holdings_list = []
            for field in record.get_fields("988"):
                holdings_list.append(
                    {
                        "call_number": field.get("a", ""),
                        "location_name": field.get("b", ""),
                        "location_code": field.get("c", ""),
                    }
                )

            call_numbers = " | ".join(
                h["call_number"] for h in holdings_list if h["call_number"]
            )
            location_names = " | ".join(
                dict.fromkeys(
                    h["location_name"] for h in holdings_list if h["location_name"]
                )
            )
            location_codes = " | ".join(
                dict.fromkeys(
                    h["location_code"] for h in holdings_list if h["location_code"]
                )
            )

            for field in record.get_fields("989"):
                rows.append(
                    {
                        "instance_hrid": instance_hrid,
                        "title": instance_title,
                        "call_number": call_numbers,
                        "location_name": location_names,
                        "location_code": location_codes,
                        "item_enumeration": field.get("h", ""),
                        "item_barcode": field.get("i", ""),
                        "item_hrid": field.get("0", ""),
                    }
                )

    return rows


def write_csv(rows, output_path):
    """Writes a list of row dicts to a CSV file.

    Args:
        rows (list[dict]): List of dicts as returned by parse_marc(). Each
            dict must contain the keys: instance_hrid, title, call_number,
            location_name, location_code, item_enumeration, item_barcode,
            and item_hrid.
        output_path (str): Path to the CSV file to write. Will be created or
            overwritten.
    """
    fieldnames = [
        "instance_hrid",
        "title",
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
    """Parses command-line arguments and runs the MARC-to-CSV conversion.

    Expects one required argument (input .mrc file path) and one optional
    argument (output .csv file path). If the output path is omitted, the
    CSV is written alongside the input file with a .csv extension.

    Raises:
        SystemExit: If no input file argument is provided.
    """
    if len(sys.argv) < 2:
        print("Usage: python marc_to_csv.py input.mrc [output.csv]")
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
