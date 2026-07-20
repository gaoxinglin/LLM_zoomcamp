import os
from typing import Any

import httpx
import pandas as pd
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="NZ Regional Insights Assistant", page_icon="🇳🇿", layout="wide")


def api(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    with httpx.Client(timeout=45) as client:
        response = client.request(method, f"{API_URL}{path}", json=payload)
        response.raise_for_status()
        return response.json() if response.content else None


def source_card(citation: dict[str, Any], number: int) -> None:
    with st.container(border=True):
        st.markdown(f"**[{number}] [{citation['title']}]({citation['url']})**")
        updated = citation.get("updated") or "not stated"
        st.caption(f"Publisher: {citation['publisher']} · Updated: {updated}")


def render_chat() -> None:
    st.subheader("Ask about Auckland open data")
    st.write(
        "Find population, housing, and transport datasets in plain English. "
        "Answers cite catalogue records and do not invent values from unseen data."
    )
    examples = [
        "Where can I find Auckland population data by local board?",
        "Which open datasets describe Auckland bus services?",
        "Find road and traffic datasets published by Auckland Council.",
    ]
    columns = st.columns(len(examples))
    for column, example in zip(columns, examples, strict=True):
        if column.button(example, use_container_width=True):
            st.session_state.question = example

    question = st.text_input("Question", key="question", placeholder="Ask for a dataset or source…")
    mode = st.selectbox("Retrieval mode", ["lexical", "hybrid", "vector"])
    if st.button("Find evidence", type="primary", disabled=not question):
        try:
            with st.spinner("Searching the catalogue index…"):
                result = api(
                    "POST",
                    "/answer",
                    {"query": question, "mode": mode, "limit": 5, "rewrite": False, "rerank": True},
                )
            st.session_state.last_answer = result
        except Exception as error:
            st.error(f"The request failed: {error}")

    result = st.session_state.get("last_answer")
    if not result:
        return
    st.markdown(result["answer"])
    st.caption(
        f"Request {result['request_id']} · {result['latency_ms']:.0f} ms · "
        f"{'LLM-assisted' if result['used_llm'] else 'extractive fallback'}"
    )
    st.markdown("#### Sources")
    for index, citation in enumerate(result["citations"], 1):
        source_card(citation, index)

    st.markdown("#### Was this useful?")
    comment = st.text_input(
        "Optional feedback",
        key=f"feedback-{result['request_id']}",
        placeholder="What worked or what was missing?",
    )
    feedback_columns = st.columns([1, 1, 5])
    for label, rating, column in (
        ("👍 Helpful", 1, feedback_columns[0]),
        ("👎 Not helpful", -1, feedback_columns[1]),
    ):
        if column.button(label):
            api(
                "POST",
                "/feedback",
                {"request_id": result["request_id"], "rating": rating, "comment": comment or None},
            )
            st.toast("Feedback saved. Thank you.")


def render_explorer() -> None:
    st.subheader("Dataset explorer")
    query = st.text_input("Search terms", "Auckland transport")
    limit = st.slider("Number of results", 1, 20, 10)
    if st.button("Search datasets"):
        try:
            results = api("POST", "/search", {"query": query, "limit": limit, "mode": "hybrid"})
            for result in results:
                dataset = result["dataset"]
                with st.expander(f"{result['rank']}. {dataset['title']}"):
                    st.write(dataset["description"] or "No description supplied.")
                    st.write(f"**Publisher:** {dataset['organization']}")
                    st.write(f"**Licence:** {dataset['license_title']}")
                    st.write(f"**Matched by:** {', '.join(result['matched_by'])}")
                    st.link_button("Open source record", dataset["url"])
        except Exception as error:
            st.error(f"Search failed: {error}")


def chart(data: list[dict[str, Any]], title: str, x: str) -> None:
    st.markdown(f"**{title}**")
    if not data:
        st.info("No data yet.")
        return
    frame = pd.DataFrame(data)
    st.bar_chart(frame, x=x, y="value", use_container_width=True)


def render_dashboard() -> None:
    st.subheader("Quality and operations dashboard")
    st.caption("Metrics are generated from anonymous local application events and feedback.")
    try:
        metrics = api("GET", "/metrics")
    except Exception as error:
        st.error(f"Metrics could not be loaded: {error}")
        return
    left, right = st.columns(2)
    with left:
        chart(metrics["requests_by_day"], "Requests by day", "day")
        chart(metrics["feedback"], "User feedback", "label")
        chart(metrics["errors_by_day"], "Errors by day", "day")
        chart(metrics["empty_results"], "Result availability", "label")
    with right:
        chart(metrics["latency_by_day"], "Average latency (ms)", "day")
        chart(metrics["search_modes"], "Retrieval modes", "label")
        chart(metrics["llm_usage"], "LLM tokens by day", "day")


st.title("🇳🇿 NZ Regional Insights Assistant")
st.warning(
    "Independent student project — not an official New Zealand Government service. "
    "Verify important conclusions against the linked source data."
)
chat_tab, explorer_tab, dashboard_tab, about_tab = st.tabs(
    ["Assistant", "Dataset explorer", "Monitoring", "About"]
)
with chat_tab:
    render_chat()
with explorer_tab:
    render_explorer()
with dashboard_tab:
    render_dashboard()
with about_tab:
    st.markdown(
        """
        This application indexes metadata from the New Zealand Government Data Catalogue and uses
        lexical and deterministic vector retrieval to recommend relevant Auckland datasets. When an
        OpenAI key is configured, the final catalogue-grounded response may be rewritten by an LLM.
        Without a key, the application remains fully usable through its extractive answer mode.

        Catalogue content remains subject to each publisher's licence, definitions, update schedule,
        and quality limitations.
        """
    )
