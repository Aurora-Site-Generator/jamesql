import json
import sys
from contextlib import ExitStack as DoesNotRaise

import pytest
from deepdiff import DeepDiff

from jamesql import JameSQL
from jamesql.index import GSI_INDEX_STRATEGIES


def pytest_addoption(parser):
    parser.addoption("--benchmark", action="store")


@pytest.fixture(scope="session")
def create_indices(request):
    with open("tests/fixtures/documents_with_numeric_values.json") as f:
        documents = json.load(f)

    index = JameSQL()

    for document in documents:
        index.add(document)

    with open("tests/fixtures/documents_with_numeric_values.json") as f:
        documents = json.load(f)

    index.create_gsi("title", strategy=GSI_INDEX_STRATEGIES.CONTAINS)
    index.create_gsi("lyric", strategy=GSI_INDEX_STRATEGIES.CONTAINS)
    index.create_gsi("listens", strategy=GSI_INDEX_STRATEGIES.NUMERIC)

    if request.config.getoption("--benchmark") or request.config.getoption(
        "--long-benchmark"
    ):
        large_index = JameSQL()

        for document in documents * 100000:
            if request.config.getoption("--long-benchmark"):
                document = document.copy()
                document["title"] = "".join(
                    [
                        word + " "
                        for word in document["title"].split()
                        for _ in range(10)
                    ]
                )
            large_index.add(document)

        large_index.create_gsi("title", strategy=GSI_INDEX_STRATEGIES.CONTAINS)
        large_index.create_gsi("lyric", strategy=GSI_INDEX_STRATEGIES.CONTAINS)
        large_index.create_gsi("listens", strategy=GSI_INDEX_STRATEGIES.NUMERIC)
    else:
        large_index = None

    return index, large_index


@pytest.mark.parametrize(
    "query, highlights, number_of_documents_expected, top_result_value, raises_exception",
    [
        (
            {
                "query": {
                    "and": [
                        {
                            "lyric": {
                                "contains": "kiss",
                                "highlight": "lyric",
                                "strict": True,
                            }
                        }
                    ]
                },
                "limit": 10,
                "sort_by": "title",
            },
            [["Started with a kiss"]],
            1,
            "The Bolter",
            DoesNotRaise(),
        ),  # test range query
    ],
)
@pytest.mark.timeout(20)
def test_search(
    create_indices,
    query,
    highlights,
    number_of_documents_expected,
    top_result_value,
    raises_exception,
):
    with raises_exception:
        index, large_index = create_indices

        response = index.search(query)

        assert len(response["documents"]) == number_of_documents_expected

        for actual_context, expected_context in zip(response["documents"], highlights):
            assert actual_context["_context"] == expected_context

        if number_of_documents_expected > 0:
            assert response["documents"][0]["title"] == top_result_value

        assert float(response["query_time"]) < 0.06

        # run if --benchmark is passed
        if "--benchmark" in sys.argv:
            response = large_index.search(query)

            assert float(response["query_time"]) < 0.06
