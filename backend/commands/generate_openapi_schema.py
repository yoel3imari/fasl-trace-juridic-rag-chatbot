"""
Generate openapi.json from the FastAPI application.

Usage:
    OPENAPI_OUTPUT_FILE=./openapi.json python -m commands.generate_openapi_schema

This script imports the FastAPI app, calls app.openapi(), and writes the
resulting schema to a JSON file.  The output path can be controlled via the
OPENAPI_OUTPUT_FILE environment variable (default: ./openapi.json).
"""

import json
import os
from pathlib import Path

from main import app


def generate_openapi_schema(output_path: str | None = None) -> str:
    """
    Generate and write the OpenAPI schema to a JSON file.

    Parameters
    ----------
    output_path : str, optional
        Filesystem path for the output file.  If not provided, the
        OPENAPI_OUTPUT_FILE environment variable is consulted.  If that is
        also unset, ``./openapi.json`` is used as the default.

    Returns
    -------
    str
        The resolved absolute path of the written file.
    """
    if output_path is None:
        output_path = os.getenv("OPENAPI_OUTPUT_FILE", "./openapi.json")

    path = Path(output_path)

    # Resolve relative paths against the current working directory.
    if not path.is_absolute():
        path = Path.cwd() / path

    schema = app.openapi()

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    print(f"OpenAPI schema written to {path}")
    return str(path)


if __name__ == "__main__":
    generate_openapi_schema()
