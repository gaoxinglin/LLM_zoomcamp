"""Configure Logfire before importing the Pydantic AI agent."""

import logfire


def configure_observability() -> None:
    # This sends remotely when LOGFIRE_TOKEN exists and stays local in tests.
    logfire.configure(
        send_to_logfire="if-token-present",
        service_name="llm-zoomcamp-dlt-homework",
    )
    logfire.instrument_pydantic_ai()

