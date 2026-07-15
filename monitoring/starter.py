"""Build the course-lessons RAG used by the monitoring homework."""

from gitsource import GithubRepositoryDataReader
from minsearch import Index
from openai import OpenAI

from rag_helper import RAGBase

COMMIT = "8c1834d"


def build_index():
    reader = GithubRepositoryDataReader(
        repo_owner="DataTalksClub",
        repo_name="llm-zoomcamp",
        commit_id=COMMIT,
        allowed_extensions={"md"},
        filename_filter=lambda path: "/lessons/" in path,
    )
    documents = [file.parse() for file in reader.read()]
    index = Index(text_fields=["content"], keyword_fields=["filename"])
    index.fit(documents)
    return index


def build_rag():
    return RAGBase(index=build_index(), llm_client=OpenAI())


if __name__ == "__main__":
    query = "How does the agentic loop keep calling the model until it stops?"
    print(build_rag().rag(query))

