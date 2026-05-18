"""Daily smoke test asserting the ASU Class Search response shape hasn't drifted.

Placeholder for M1.0 — fills in during M1.1 once the parser exists. The real
test will load `tests/fixtures/cse_fall26_sample.json`, pull a fresh page from
the live API, and assert the field set hasn't shrunk.
"""

import pytest


@pytest.mark.skip(reason="Implemented in M1.1 once the parser exists.")
def test_schema_drift() -> None:
    raise NotImplementedError
