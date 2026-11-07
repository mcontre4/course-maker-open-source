import pytest

from app.courses.domain.content_search import matches_search, search_rank


@pytest.mark.parametrize("query", ["cafe", "CAFÉ", "  cafe   alg  "])
def test_search_matches_partial_words_case_accents_and_whitespace(query):
    assert matches_search(query, "Café algebra")
    assert not matches_search(query, "Unrelated title")


def test_title_rank_prioritizes_exact_then_prefix_then_contained_matches():
    titles = ["Python", "Python basics", "Learn Python", "Programming"]
    assert [search_rank("python", title) for title in titles] == [0, 1, 2, 3]
