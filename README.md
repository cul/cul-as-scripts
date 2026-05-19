# CUL ArchivesSpace Scripts

Scripts for interacting with the Columbia University Libraries ArchivesSpace
instance on an ad-hoc basis. Includes tools for managing access restrictions,
container data, digital objects, locations, and metadata exports.

## Requirements

- Python 3.10+
- See `requirements.txt` for dependencies

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Create a credentials file by renaming `local_settings.cfg.example` to
   `local_settings.cfg` and updating it with your ArchivesSpace credentials
   and base URL.
3. Install pre-commit hooks: `pre-commit install`

## Scripts

| Script                        | Description                                                          |
| ----------------------------- | -------------------------------------------------------------------- |
| `add_containers.py`           | Propagates container instance data to archival objects missing it    |
| `add_dlc_dos.py`              | Creates and attaches IIIF digital objects to archival objects        |
| `add_locations.py`            | Adds location data to top containers                                 |
| `add_metadata_rights.py`      | Adds metadata rights declarations to published resources             |
| `get_aspace_barcodes.py`      | Fetches top container barcodes using FOLIO HRIDs                     |
| `reorder_one_series.py`       | Identifies and removes redundant single-series structure             |
| `restriction_lifter.py`       | Exports and removes expired access restriction notes                 |
| `update_access_notes.py`      | Updates access restriction note text across a series or repository   |
| `update_hyacinth_metadata.py` | Exports archival object metadata for Hyacinth import                 |
| `update_instances.py`         | Disambiguates box numbers by adding prefixes to container indicators |

## Contribution standards

### Style

This project follows [PEP 8](https://peps.python.org/pep-0008/) style guidelines,
enforced in VS Code via the following extensions:

- **[black](https://black.readthedocs.io/)** — formats code automatically on save
- **[isort](https://pycqa.github.io/isort/)** — sorts imports alphabetically and by
  type on save, using the `black` profile for compatibility
- **[flake8](https://flake8.pycqa.org/)** — checks for style issues, errors, and
  complexity; configured via `.flake8`

To replicate this setup, install the
[Black Formatter](https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter),
[isort](https://marketplace.visualstudio.com/items?itemName=ms-python.isort), and
[Flake8](https://marketplace.visualstudio.com/items?itemName=ms-python.flake8)
VS Code extensions. Project settings are in `.vscode/settings.json`.

### Documentation

Docstrings follow [Google's docstring style guide](https://google.github.io/styleguide/pyguide.html#381-docstrings). Use one-line docstrings for immediately self-explanatory cases; use multi-line docstrings for everything else.

### Tests

New code should have unit tests. Tests are written using [pytest](https://docs.pytest.org/) and [pytest-mock](https://pytest-mock.readthedocs.io/), and run via [tox](https://tox.readthedocs.io/). To run the tests and coverage report:

```bash
tox -e py311
```
