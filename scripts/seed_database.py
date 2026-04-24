from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import json_util
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED_DIR = PROJECT_ROOT / "scripts" / "seed" / "ecommerce_db"
EXCLUDED_COLLECTION_PREFIXES = ("system.",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export or import every MongoDB collection for repeatable Docker dev seeding."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export all collections from a MongoDB database.")
    export_parser.add_argument("--source-uri", required=True, help="MongoDB URI to export from.")
    export_parser.add_argument("--source-db", required=True, help="Database name to export from.")
    export_parser.add_argument("--out-dir", default=str(DEFAULT_SEED_DIR), help="Directory to write seed files into.")

    import_parser = subparsers.add_parser("import", help="Import all exported collections into a MongoDB database.")
    import_parser.add_argument("--target-uri", required=True, help="MongoDB URI to import into.")
    import_parser.add_argument("--target-db", required=True, help="Database name to import into.")
    import_parser.add_argument("--in-dir", default=str(DEFAULT_SEED_DIR), help="Directory containing seed files.")
    import_parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop target collections before importing. Recommended for deterministic local dev seeding.",
    )

    return parser.parse_args()


def is_exportable_collection(name: str) -> bool:
    return not name.startswith(EXCLUDED_COLLECTION_PREFIXES)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=json_util.default), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_hook=json_util.object_hook)


def export_database(source_uri: str, source_db_name: str, out_dir: Path) -> dict[str, int]:
    client = MongoClient(source_uri, tz_aware=True)
    db = client[source_db_name]

    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    collection_names = sorted(name for name in db.list_collection_names() if is_exportable_collection(name))

    for collection_name in collection_names:
        documents = list(db[collection_name].find({}))
        write_json(out_dir / f"{collection_name}.json", documents)
        counts[collection_name] = len(documents)

    metadata = {
        "source_uri": source_uri,
        "source_db": source_db_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "collections": counts,
    }
    write_json(out_dir / "_metadata.json", metadata)
    client.close()
    return counts


def import_database(target_uri: str, target_db_name: str, in_dir: Path, *, drop: bool) -> dict[str, int]:
    if not in_dir.exists():
        raise SystemExit(f"Seed directory does not exist: {in_dir}")

    client = MongoClient(target_uri, tz_aware=True)
    db = client[target_db_name]

    counts: dict[str, int] = {}
    seed_files = sorted(path for path in in_dir.glob("*.json") if path.name != "_metadata.json")

    for seed_file in seed_files:
        collection_name = seed_file.stem
        documents = read_json(seed_file)
        if not isinstance(documents, list):
            raise SystemExit(f"Seed file must contain a JSON array: {seed_file}")

        collection = db[collection_name]
        if drop:
            collection.drop()

        if documents:
            collection.insert_many(documents, ordered=False)

        counts[collection_name] = len(documents)

    client.close()
    return counts


def main() -> int:
    args = parse_args()

    if args.command == "export":
        counts = export_database(args.source_uri, args.source_db, Path(args.out_dir))
        print(f"Exported collections to {args.out_dir}: {counts}")
        return 0

    if args.command == "import":
        counts = import_database(args.target_uri, args.target_db, Path(args.in_dir), drop=args.drop)
        print(f"Imported collections from {args.in_dir}: {counts}")
        return 0

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
