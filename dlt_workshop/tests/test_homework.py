import duckdb

from analyze import count_tables, input_tokens_for_question, token_range
from ingest import build_index


def test_search_index_filters_to_llm_zoomcamp():
    documents = [
        {
            "course": "llm-zoomcamp",
            "question": "How can I run Ollama locally?",
            "section": "Module 1",
            "answer": "Install Ollama, then run ollama serve.",
        },
        {
            "course": "other-course",
            "question": "How can I run Ollama locally?",
            "section": "Setup",
            "answer": "Not the target course.",
        },
    ]
    results = build_index(documents).search(
        "run Ollama locally",
        num_results=5,
        filter_dict={"course": "llm-zoomcamp"},
    )
    assert len(results) == 1
    assert results[0]["course"] == "llm-zoomcamp"


def test_table_count_and_token_ranges():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA agent_traces")
    conn.execute("CREATE TABLE agent_traces.records(id INTEGER)")
    conn.execute("CREATE TABLE agent_traces.child(id INTEGER)")
    assert count_tables(conn) == 2
    assert token_range(3000) == "1500 - 5000"
    assert token_range(9000) == "outside the supplied ranges"


def test_input_tokens_are_summed_across_llm_spans():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA agent_traces")
    conn.execute(
        '''
        CREATE TABLE agent_traces.records (
            trace_id VARCHAR,
            message VARCHAR,
            "attributes__gen_ai__usage__input_tokens" INTEGER
        )
        '''
    )
    conn.execute(
        '''
        INSERT INTO agent_traces.records VALUES
            ('target', 'How do I run Ollama locally?', NULL),
            ('target', 'model request 1', 1700),
            ('target', 'model request 2', 1800),
            ('other', 'another question', 400)
        '''
    )

    trace_id, tokens = input_tokens_for_question(
        conn,
        "How do I run Ollama locally?",
    )
    assert trace_id == "target"
    assert tokens == 3500
