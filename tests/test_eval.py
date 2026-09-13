import json
from pathlib import Path


def test_retrieval_evaluation_set_has_eight_questions():
    data = json.loads(Path("evaluation/questions.json").read_text())
    assert len(data) >= 8
    assert all(item["expected_sources"] for item in data)
