import sys

from scripts.aspace_barcodes import AspaceBarcodeFetcher


def main():
    if len(sys.argv) != 3:
        print("Usage: python aspace_barcodes_to_csv.py <folio_csv> <output_csv>")
        sys.exit(1)
    folio_csv_path = sys.argv[1]
    output_path = sys.argv[2]
    fetcher = AspaceBarcodeFetcher(mode="prod")
    fetcher.run(folio_csv_path, output_path)


if __name__ == "__main__":
    main()
