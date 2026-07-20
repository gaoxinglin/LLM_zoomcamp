import hashlib
import html
import math
import re
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9]+")
TAG_RE = re.compile(r"<[^>]+>")


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(html.unescape(TAG_RE.sub(" ", value)).split())


def tokens(value: str) -> list[str]:
    return TOKEN_RE.findall(value.lower())


def hash_embedding(value: str, dimensions: int = 256) -> list[float]:
    """Create a deterministic, dependency-free feature-hashing embedding."""
    counts: Counter[int] = Counter()
    for token in tokens(value):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % dimensions
        sign = 1 if digest[0] % 2 == 0 else -1
        counts[index] += sign
    vector = [float(counts[index]) for index in range(dimensions)]
    norm = math.sqrt(sum(item * item for item in vector)) or 1.0
    return [item / norm for item in vector]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


QUERY_SYNONYMS = {
    "homes": "housing dwellings residential",
    "house": "housing dwelling residential",
    "people": "population residents demographic",
    "residents": "population demographic",
    "traffic": "transport roads vehicles traffic",
    "train": "rail railway public transport",
    "bus": "public transport transit bus",
    "bike": "cycling cycle bicycle",
    "auckland": "tāmaki makaurau local board",
}


def rewrite_query(query: str) -> str:
    additions = [expanded for word, expanded in QUERY_SYNONYMS.items() if word in tokens(query)]
    return " ".join([query, *additions]).strip()
