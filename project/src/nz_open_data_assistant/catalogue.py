import json
import re
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import DataQueryPlan, DataQueryResult, Dataset, Resource
from .text import clean_html


class CatalogueError(RuntimeError):
    pass


class CatalogueClient:
    def __init__(self, base_url: str, timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "CatalogueClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=6), reraise=True)
    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("success") is False:
            raise CatalogueError(str(payload.get("error", "Catalogue request failed")))
        return payload

    def search(self, query: str, rows: int = 100, start: int = 0) -> tuple[int, list[Dataset]]:
        payload = self._get(
            f"{self.base_url}/api/3/action/package_search",
            {"q": query, "rows": min(rows, 1000), "start": start},
        )
        result = payload["result"]
        return int(result["count"]), [self._parse_dataset(item) for item in result["results"]]

    def package(self, dataset_id: str) -> Dataset:
        payload = self._get(
            f"{self.base_url}/api/3/action/package_show",
            {"id": dataset_id},
        )
        return self._parse_dataset(payload["result"])

    def ckan_fields(self, resource_id: str) -> list[str]:
        payload = self._get(
            f"{self.base_url}/api/3/action/datastore_search",
            {"resource_id": resource_id, "limit": 0},
        )
        return [field["id"] for field in payload["result"].get("fields", [])]

    def arcgis_fields(self, service_url: str) -> list[str]:
        payload = self._get(service_url, {"f": "json"})
        if "error" in payload:
            raise CatalogueError(str(payload["error"]))
        return [field["name"] for field in payload.get("fields", [])]

    def execute_query(self, plan: DataQueryPlan, dataset: Dataset) -> DataQueryResult:
        resource = next((item for item in dataset.resources if item.id == plan.resource_id), None)
        if resource is None:
            raise CatalogueError("The resource is not registered for this dataset")

        if plan.adapter == "ckan":
            return self._query_ckan(plan, resource)
        return self._query_arcgis(plan, resource)

    def _query_ckan(self, plan: DataQueryPlan, resource: Resource) -> DataQueryResult:
        allowed = set(self.ckan_fields(resource.id))
        self._validate_fields(plan, allowed)
        if any(item.operator not in {"=", "!="} for item in plan.filters):
            raise CatalogueError("CKAN queries currently support only equality filters")

        filters = {item.field: item.value for item in plan.filters if item.operator == "="}
        params: dict[str, Any] = {
            "resource_id": resource.id,
            "limit": plan.limit,
            "filters": json.dumps(filters),
        }
        if plan.fields:
            params["fields"] = ",".join(plan.fields)
        if plan.order_by:
            params["sort"] = f"{plan.order_by} {'desc' if plan.descending else 'asc'}"
        payload = self._get(f"{self.base_url}/api/3/action/datastore_search", params)
        rows = payload["result"].get("records", [])
        columns = list(rows[0]) if rows else plan.fields
        return DataQueryResult(
            plan=plan,
            columns=columns,
            rows=rows,
            source_url=resource.url,
            row_count=len(rows),
        )

    def _query_arcgis(self, plan: DataQueryPlan, resource: Resource) -> DataQueryResult:
        service_url = resource.url.rstrip("/")
        allowed = set(self.arcgis_fields(service_url))
        self._validate_fields(plan, allowed)
        where = " AND ".join(self._arcgis_filter(item, allowed) for item in plan.filters) or "1=1"
        params: dict[str, Any] = {
            "f": "json",
            "where": where,
            "outFields": ",".join(plan.fields) if plan.fields else "*",
            "returnGeometry": "false",
            "resultRecordCount": plan.limit,
        }
        if plan.order_by:
            params["orderByFields"] = f"{plan.order_by} {'DESC' if plan.descending else 'ASC'}"
        payload = self._get(f"{service_url}/query", params)
        if "error" in payload:
            raise CatalogueError(str(payload["error"]))
        rows = [feature.get("attributes", {}) for feature in payload.get("features", [])]
        columns = list(rows[0]) if rows else plan.fields
        return DataQueryResult(
            plan=plan,
            columns=columns,
            rows=rows,
            source_url=resource.url,
            row_count=len(rows),
        )

    @staticmethod
    def _validate_fields(plan: DataQueryPlan, allowed: set[str]) -> None:
        requested = set(plan.fields)
        requested.update(item.field for item in plan.filters)
        if plan.order_by:
            requested.add(plan.order_by)
        unknown = requested - allowed
        if unknown:
            raise CatalogueError(f"Unsupported fields: {', '.join(sorted(unknown))}")

    @staticmethod
    def _arcgis_filter(filter_: Any, allowed: set[str]) -> str:
        if filter_.field not in allowed:
            raise CatalogueError(f"Unsupported field: {filter_.field}")
        operator = "LIKE" if filter_.operator == "contains" else filter_.operator
        value = filter_.value
        if isinstance(value, str):
            escaped = value.replace("'", "''")
            value_sql = f"'%{escaped}%'" if operator == "LIKE" else f"'{escaped}'"
        elif isinstance(value, bool):
            value_sql = "1" if value else "0"
        else:
            value_sql = str(value)
        return f"{filter_.field} {operator} {value_sql}"

    def _parse_dataset(self, item: dict[str, Any]) -> Dataset:
        organization = item.get("organization") or {}
        dataset_id = str(item["id"])
        dataset_name = str(item.get("name") or dataset_id)
        public_url = item.get("url") or f"{self.base_url}/dataset/{dataset_name}"
        resources = [
            Resource(
                id=str(resource["id"]),
                name=resource.get("name") or "Resource",
                url=resource.get("url") or "",
                format=(resource.get("format") or "").strip(),
                datastore_active=bool(resource.get("datastore_active")),
            )
            for resource in item.get("resources", [])
            if resource.get("url")
        ]
        return Dataset(
            id=dataset_id,
            name=dataset_name,
            title=item.get("title") or dataset_name,
            description=clean_html(item.get("notes")),
            organization=organization.get("title") or item.get("author") or "Unknown publisher",
            tags=[tag.get("display_name") or tag.get("name", "") for tag in item.get("tags", [])],
            groups=[
                group.get("display_name") or group.get("title", "")
                for group in item.get("groups", [])
            ],
            license_title=item.get("license_title") or item.get("license_id") or "Not specified",
            metadata_created=item.get("metadata_created"),
            metadata_modified=item.get("metadata_modified") or item.get("modified"),
            url=public_url,
            resources=resources,
        )


def looks_like_arcgis(resource: Resource) -> bool:
    return bool(
        re.search(r"/(?:FeatureServer|MapServer)/\d+/?$", resource.url, re.IGNORECASE)
        or "ArcGIS GeoServices" in resource.format
        or "Esri REST" in resource.format
    )
