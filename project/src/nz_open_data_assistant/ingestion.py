import argparse
import json
import logging
from pathlib import Path

from .catalogue import CatalogueClient
from .config import get_settings
from .models import Dataset
from .storage import Storage

LOGGER = logging.getLogger(__name__)

TOPIC_QUERIES = {
    "population": "Auckland population",
    "housing": "Auckland housing",
    "transport": "Auckland transport",
}
TOPIC_TERMS = {
    "population": {"population", "demographic", "residents", "census", "ethnic", "age"},
    "housing": {"housing", "dwelling", "building", "residential", "home", "property"},
    "transport": {
        "transport",
        "traffic",
        "road",
        "bus",
        "train",
        "rail",
        "cycling",
        "ferry",
        "parking",
    },
}
PUBLIC_PUBLISHER_MARKERS = {
    "council",
    "stats nz",
    "ministry",
    "department",
    "agency",
    "new zealand transport",
    "land information",
}


def relevant(dataset: Dataset, topic: str) -> bool:
    content = " ".join(
        [dataset.title, dataset.description, " ".join(dataset.tags), " ".join(dataset.groups)]
    ).lower()
    auckland = dataset.organization.lower() == "auckland council" or any(
        phrase in content
        for phrase in (
            "auckland region",
            "auckland city",
            "auckland local",
            "auckland transport",
            "auckland council",
            "tāmaki makaurau",
        )
    )
    public_publisher = any(
        marker in dataset.organization.lower() for marker in PUBLIC_PUBLISHER_MARKERS
    )
    return auckland and public_publisher and any(term in content for term in TOPIC_TERMS[topic])


def load_seed(path: Path) -> list[Dataset]:
    return [Dataset.model_validate(item) for item in json.loads(path.read_text())]


def ingest(
    storage: Storage,
    seed_path: Path,
    max_per_topic: int = 200,
    seed_only: bool = False,
    replace: bool = False,
) -> dict[str, int]:
    if replace:
        storage.clear_datasets()
    seen: set[str] = set()
    seen_signatures: set[tuple[str, str]] = set()
    counts = {"seed": 0, "population": 0, "housing": 0, "transport": 0}
    for dataset in load_seed(seed_path):
        storage.upsert_dataset(dataset)
        seen.add(dataset.id)
        seen_signatures.add((dataset.title.casefold(), dataset.organization.casefold()))
        counts["seed"] += 1

    if seed_only:
        return counts

    settings = get_settings()
    with CatalogueClient(
        settings.catalogue_base_url, settings.request_timeout_seconds
    ) as catalogue:
        for topic, query in TOPIC_QUERIES.items():
            start = 0
            total = max_per_topic
            while start < min(total, max_per_topic):
                page_size = min(100, max_per_topic - start)
                try:
                    total, datasets = catalogue.search(query, rows=page_size, start=start)
                except Exception:
                    LOGGER.exception(
                        "Could not fetch the %s topic; seeded data remain available", topic
                    )
                    break
                if not datasets:
                    break
                start += len(datasets)
                for dataset in datasets:
                    signature = (dataset.title.casefold(), dataset.organization.casefold())
                    if dataset.id in seen:
                        storage.upsert_dataset(dataset)
                        continue
                    if signature in seen_signatures or not relevant(dataset, topic):
                        continue
                    storage.upsert_dataset(dataset)
                    seen.add(dataset.id)
                    seen_signatures.add(signature)
                    counts[topic] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Auckland open-data metadata")
    parser.add_argument("--max-per-topic", type=int, default=200)
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--database", type=Path)
    parser.add_argument(
        "--seed-file",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "seed_datasets.json",
    )
    arguments = parser.parse_args()
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    counts = ingest(
        Storage(arguments.database or settings.database_path),
        arguments.seed_file,
        arguments.max_per_topic,
        arguments.seed_only,
        arguments.replace,
    )
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
