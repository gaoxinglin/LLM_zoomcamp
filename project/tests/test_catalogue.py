import pytest

from nz_open_data_assistant.catalogue import CatalogueClient, CatalogueError
from nz_open_data_assistant.models import DataQueryPlan, Filter


def test_query_plan_rejects_unsafe_field_name() -> None:
    with pytest.raises(ValueError):
        Filter(field="name; DROP TABLE", value="Auckland")


def test_field_allowlist_rejects_unknown_fields() -> None:
    plan = DataQueryPlan(
        dataset_id="dataset",
        resource_id="resource",
        adapter="arcgis",
        fields=["unsafe"],
    )
    with pytest.raises(CatalogueError, match="Unsupported fields"):
        CatalogueClient._validate_fields(plan, {"safe"})


def test_arcgis_filter_escapes_quotes() -> None:
    filter_ = Filter(field="name", operator="=", value="O'Brien")
    assert CatalogueClient._arcgis_filter(filter_, {"name"}) == "name = 'O''Brien'"
