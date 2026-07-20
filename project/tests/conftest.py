import json
from pathlib import Path

import pytest

from nz_open_data_assistant.models import Dataset
from nz_open_data_assistant.storage import Storage


@pytest.fixture
def seed_datasets() -> list[Dataset]:
    path = Path(__file__).parents[1] / "data" / "seed_datasets.json"
    return [Dataset.model_validate(item) for item in json.loads(path.read_text())]


@pytest.fixture
def storage(tmp_path: Path, seed_datasets: list[Dataset]) -> Storage:
    instance = Storage(tmp_path / "test.db")
    for dataset in seed_datasets:
        instance.upsert_dataset(dataset)
    return instance
