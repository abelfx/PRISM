"""Tier 2 public modules must be importable without import-order dependence."""


def test_tier2_client_imports_before_search_package():
    from prism.tier2.client import MockLLMClient

    assert MockLLMClient is not None
