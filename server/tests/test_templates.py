import json
from pathlib import Path

import pytest

from flowmuse.templates import TemplateError, merge_variables, resolve_template

CASES = json.loads((Path(__file__).resolve().parents[2] / "web/tests/fixtures/templateCases.json").read_text("utf-8"))


@pytest.mark.parametrize("case", CASES)
def test_shared_template_syntax(case):
    if case.get("error"):
        with pytest.raises(TemplateError, match="未定义变量"):
            resolve_template(case["source"], variables=case["context"])
    else:
        assert resolve_template(case["source"], variables=case["context"]) == case["expected"].strip()


def test_variable_override_and_expansion_budgets():
    inherited = {"story": "original", "style": "watercolor"}
    assert merge_variables(inherited, {"story": "new"}) == {"story": "new", "style": "watercolor"}
    assert inherited["story"] == "original"
    with pytest.raises(TemplateError, match="超过限制"):
        merge_variables({f"v{i}": "x" for i in range(50)}, {"extra": "x"})
    with pytest.raises(TemplateError, match="超过限制"):
        merge_variables({"x": "a" * 20000}, {"y": "b" * 20000})
    with pytest.raises(TemplateError, match="32000"):
        resolve_template("{x}{x}", variables={"x": "a" * 20000})
