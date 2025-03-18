# MedConB Client

[![Build Status](https://github.com/Bayer-Group/medconb-client/actions/workflows/ci.yaml/badge.svg)](https://github.com/Bayer-Group/medconb-client/actions)
[![Documentation](https://img.shields.io/badge/Documentation-526CFE?logo=MaterialForMkDocs&logoColor=white)](https://bayer-group.github.io/medconb-client/)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

This library provides a Python interface to the MedConB API. With this you can easily retrieve whole codelists from MedConB.

## Installation

You can install (and update) it into your python environment by running:

```
pip install --force-reinstall -U medconb-client
```

## Usage

To use it, you need to create a client:

```python
from medconb_client import Client

endpoint = "https://api.medconb.example.com/graphql/"
token = get_token()

client = Client(endpoint, token)
```

with that client you can now interact with the API.

### Get a codelist by name

```python
codelist = client.get_codelist_by_name(
    codelist_name="Coronary Artery Disease",
    codelist_collection_name="Pacific AF [Sample]",
)
```

```python
codelist = client.get_codelist_by_name(
    codelist_name="Coronary Artery Disease",
    phenotype_collection_name="[Sample] PACIFIC AF ECA",
    phenotype_name="Coronary Artery Disease",
)
```

### Get a codelist by id

```python
codelist = client.get_codelist(
    codelist_id="9c4ad312-3008-4d95-9b16-6f9b21ec1ad9"
)
```

### Retrieve collections in your workspace

```python
workspace_info = client.get_workspace()

collection_info = next(
    collection
    for collection in workspace_info.collections
    if collection.itemType == "Codelist"
)

codelist = client.get_codelist(collection_info.items[0].id)
```

For more information, also see our [Examples Page](https://refactored-adventure-kgjn1rq.pages.github.io/examples/).
