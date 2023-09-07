# datasette-short-links

[![PyPI](https://img.shields.io/pypi/v/datasette-short-links.svg)](https://pypi.org/project/datasette-short-links/)
[![Changelog](https://img.shields.io/github/v/release/datasette/datasette-short-links?include_prereleases&label=changelog)](https://github.com/datasette/datasette-short-links/releases)
[![Tests](https://github.com/datasette/datasette-short-links/workflows/Test/badge.svg)](https://github.com/datasette/datasette-short-links/actions?query=workflow%3ATest)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/datasette/datasette-short-links/blob/main/LICENSE)

A URL link shortener for Datasette. Work in progress!

## Installation

This plugin requires an alpha version of Datasette 1.0, because it uses [Datasette's internal database](https://docs.datasette.io/en/latest/internals.html#internals-internal) introduced in `1.0a5`.

    pip install datasette==1.0a5

After than, you can install this plugin in the same environment as Datasette.

    datasette install datasette-short-links

## Usage

Once installed, the bottom of each page with have a "Copy URL" button at the bottom of that page. That URL will link directly back to the same page.

A short URL will look something like: `http://localhost:8001/-/l/01h973jcqspxrhzy00zebhx748`

To take full advantage of this plugin, use a persistent internal database to store links even after your Datasette instance exits. This can be done with the `--internal` flag:

```
datasette --internal internal.db my_data.db
```

## Development

To set up this plugin locally, first checkout the code. Then create a new virtual environment:

    cd datasette-short-links
    python3 -m venv venv
    source venv/bin/activate

Now install the dependencies and test dependencies:

    pip install -e '.[test]'

To run the tests:

    pytest
