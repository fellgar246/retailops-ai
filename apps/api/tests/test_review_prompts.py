import pytest

from retailops_api.review.prompts import get_prompt, list_prompts, prompt_for
from retailops_api.review.types import PromptError, ReviewType


def test_every_review_type_has_a_versioned_prompt() -> None:
    specs = {item.prompt_id: item for item in list_prompts()}

    assert set(specs) == {
        "supplier.category_suggestion",
        "supplier.summary",
        "reconciliation.explanation",
    }
    for spec in specs.values():
        assert spec.version
        assert spec.purpose
        assert spec.input_schema_version
        assert spec.output_schema_version
        assert spec.template


def test_prompt_lookup_is_by_id_and_version() -> None:
    current = prompt_for(ReviewType.category_suggestion)
    loaded = get_prompt(current.prompt_id, current.version)

    assert loaded == current
    assert get_prompt(current.prompt_id).version == current.version


def test_unknown_prompt_is_an_error() -> None:
    with pytest.raises(PromptError, match="unknown prompt"):
        get_prompt("does.not.exist")
    with pytest.raises(PromptError, match="unknown prompt"):
        get_prompt("supplier.summary", "99")
