"""Write the API's OpenAPI schema. `make types` turns it into the frontend's types (D-42).

python -m app.openapi_export openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def export(path: Path) -> None:
    schema = create_app().openapi()
    path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    export(Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json"))
