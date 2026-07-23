## ADDED Requirements

### Requirement: Shared Test Fixture Layer

The test suite SHALL provide a shared `tests/conftest.py` exposing named pytest fixtures for the
setup that is otherwise repeated across test modules (writing a selection-matrix YAML to a temporary
path and staging a stub models-root), and a `tests/fixtures/` directory for committed test data.
Existing tests SHALL consume these shared fixtures for their setup **without any change to their
assertions**, and the full suite SHALL remain green. Setup that is intentionally test-specific (for
example, the deliberately malformed YAML used by error-path tests) SHALL remain inline rather than
being forced into a shared fixture.

#### Scenario: Repeated matrix setup is provided as a shared fixture

- **WHEN** a test needs a valid selection-matrix YAML written to a temporary path
- **THEN** it obtains one from a shared fixture in `tests/conftest.py`
- **AND** the previously duplicated inline setup in the migrated tests is removed while their
  assertions are unchanged

#### Scenario: Suite stays green after the setup refactor

- **WHEN** the shared fixtures replace the migrated per-module setup
- **THEN** the full test suite passes with no change in the set of assertions each test makes

#### Scenario: Intentionally-inline error inputs are not fixturized

- **WHEN** a test's purpose is to feed a specific malformed or edge-case input (for example a YAML
  file missing a required key)
- **THEN** that input remains defined inline in the test rather than being moved to a shared fixture
