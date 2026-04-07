# CUL ArchivesSpace Scripts

Scripts that are run against the ArchivesSpace API on a daily or weekly basis.

## Requirements

- Python 3.10+
- See requirements.txt

## Setup

Create a file to hold credentials and filepaths. The easiest way to do this is to rename `local_settings.cfg.example` to `local_settings.cfg` and update it with your values.

## Contribution standards

### Style

This project uses the Python PEP8 community style guidelines. To conform to these guidelines, the following linters are part of the pre-commit:

- black formats the code automatically
- flake8 checks for style problems as well as errors and complexity
- isort sorts imports alphabetically, and automatically separated into sections and by type

After locally installing pre-commit, install the git-hook scripts in the project directory: `pre-commit install`

### Documentation

This project adheres to [Google’s docstring style guide](https://google.github.io/styleguide/pyguide.html#381-docstrings). There are two types of docstrings: one-liners and multi-line docstrings. A one-line docstring may be perfectly appropriate for obvious cases where the code is immediately self-explanatory. Use multiline docstrings for all other cases.

### Tests

New code should have unit tests. Tests are written in unittest style and run using [tox](https://tox.readthedocs.io/). To run the unit tests, specify the Python version using the `e` flag (see `tox.ini` for supported versions).
