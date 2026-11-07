import unicodedata


def normalize_search(text: str) -> str:
    return " ".join(
        "".join(
            character
            for character in unicodedata.normalize("NFD", text.lower())
            if unicodedata.category(character) != "Mn"
        ).split()
    )


def matches_search(query: str, *fields: str) -> bool:
    text = normalize_search(" ".join(fields))
    return all(word in text for word in normalize_search(query).split())


def search_rank(query: str, title: str) -> int:
    query, title = normalize_search(query), normalize_search(title)
    if title == query:
        return 0
    if title.startswith(query):
        return 1
    return 2 if query in title else 3
