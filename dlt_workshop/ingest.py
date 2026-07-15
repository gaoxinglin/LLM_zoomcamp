"""Download the DataTalksClub FAQ and build the minsearch index."""

import requests
from minsearch import Index

FAQ_INDEX_URL = "https://datatalks.club/faq/json/courses.json"


def load_faq_data():
    response = requests.get(FAQ_INDEX_URL, timeout=30)
    response.raise_for_status()

    documents = []
    url_prefix = "https://datatalks.club/faq"
    for course in response.json():
        course_response = requests.get(
            f'{url_prefix}{course["path"]}',
            timeout=30,
        )
        course_response.raise_for_status()
        documents.extend(course_response.json())
    return documents


def build_index(documents):
    index = Index(
        text_fields=["question", "section", "answer"],
        keyword_fields=["course"],
    )
    index.fit(documents)
    return index

