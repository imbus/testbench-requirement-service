import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def csv_to_jsonl(csv_file_path: Path, jsonl_file_path: Path):
    # Maps CSV types to requirement boolean values
    type_to_requirement = {
        "testtheme": False,
        "testcaseset": True,
        "testcase": None,  # Ignore test cases
    }

    # Parse the CSV file
    with csv_file_path.open(encoding="cp1252") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")
        data = []
        id_to_parent = defaultdict(list)

        for row in reader:
            req_type = row["type"]
            is_requirement = type_to_requirement.get(req_type)

            if is_requirement is None:
                continue

            # Basic fields
            entry: dict = {
                "name": row["spec.name"],
                "extendedID": row["uid"],
                "key": {
                    "id": row["nr"],
                    "version": {
                        "name": row["spec.version"] or "1.0",
                        "date": row["spec.versiondate"]
                        or datetime.now(tz=timezone.utc).isoformat(),
                        "author": row["spec.versionowner"],
                        "comment": row["spec.versioncomment"],
                    },
                },
                "owner": row["spec.responsible"],
                "status": row["spec.status"],
                "priority": row["spec.priority"],
                "requirement": is_requirement,
                "description": row["spec.description"],
                "documents": [],
            }

            # Add documents from references and attachments
            references = (
                row["spec.references"].strip('"').split(",") if row["spec.references"] else []
            )
            attachments = (
                row["spec.attachments"].strip('"').split(",") if row["spec.attachments"] else []
            )
            entry["documents"] = [doc.strip() for doc in references + attachments if doc.strip()]

            # Set parent if available
            if row["parent"]:
                entry["parent"] = row["parent"]
            else:
                entry["parent"] = None

            # Add user-defined attributes
            udf_attributes = [
                {"name": key.replace("spec.UDF.", ""), "valueType": "STRING", "stringValue": value}
                for key, value in row.items()
                if key.startswith("spec.UDF.") and value
            ]
            entry["userDefinedAttributes"] = udf_attributes

            # Append the entry to the data list
            data.append(entry)
            id_to_parent[row["parent"]].append(entry)

    # Write to JSONL file
    with jsonl_file_path.open(mode="w", encoding="utf-8") as jsonlfile:
        for entry in data:
            jsonlfile.write(json.dumps(entry) + "\n")

    print(f"Conversion complete. JSONL saved to {jsonl_file_path}")


if __name__ == "__main__":
    csv_to_jsonl(Path(sys.argv[1]), Path(sys.argv[2]))
