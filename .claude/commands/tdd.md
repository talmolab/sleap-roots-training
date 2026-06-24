---
description: Test-driven development workflow for scientific software
---

# Test-Driven Development (TDD)

Structured TDD workflow for implementing features with tests first, ensuring scientific correctness and code quality.

## Purpose

TDD is critical for scientific software where correctness matters. This workflow ensures:

1. Requirements are captured as executable tests before implementation
2. Edge cases are considered upfront (NaN, empty data, boundary conditions)
3. Statistical calculations have known-answer test fixtures
4. Regressions are caught immediately

## TDD Cycle

### Phase 1: Red (Write Failing Tests)

Write tests that define the expected behavior of the new feature:

```python
# tests/test_<module>.py

import pytest
import numpy as np
import pandas as pd


class TestNewFeature:
    """Tests for <feature description>."""

    def test_basic_functionality(self, sample_data):
        """Test that the feature works with normal input."""
        result = new_function(sample_data)
        assert result is not None
        # Assert specific expected values

    def test_edge_case_empty_data(self):
        """Test behavior with empty input."""
        result = new_function(pd.DataFrame())
        assert result is empty or raises appropriate error

    def test_edge_case_nan_values(self, sample_data_with_nans):
        """Test NaN handling."""
        result = new_function(sample_data_with_nans)
        # Assert NaN values are handled correctly

    def test_known_answer(self):
        """Test with known-answer fixture for statistical correctness."""
        # Use hand-calculated or reference values
        data = create_known_answer_fixture()
        result = new_function(data)
        np.testing.assert_allclose(result.value, expected_value, rtol=1e-6)
```

### Phase 2: Confirm Red

Run the tests to confirm they fail as expected:

```bash
uv run pytest tests/test_<module>.py -v
```

All new tests should fail with `ImportError`, `AttributeError`, or `AssertionError` - not with unexpected errors. If tests fail for wrong reasons, fix the test setup first.

### Phase 3: Green (Implement the Feature)

Write the minimum code to make all tests pass:

```python
# src/sleap_roots_training/<module>.py

def new_function(data):
    """Implement the feature."""
    # Write implementation that satisfies the tests
    ...
```

Run tests again:

```bash
uv run pytest tests/test_<module>.py -v
```

All tests should pass. If not, fix the implementation (not the tests, unless the test itself was wrong).

### Phase 4: Refactor

Improve the implementation while keeping tests green:

1. Clean up code structure
2. Add type hints
3. Improve variable names
4. Extract helper functions if needed

Run tests after each refactor step:

```bash
uv run pytest tests/test_<module>.py -v
```

### Phase 5: Verify Quality

Run the full quality check suite:

```bash
# Lint check
uv run black --check src/sleap_roots_training tests && uv run ruff check src/sleap_roots_training

# Full test suite (not just new tests)
uv run pytest tests/

# Coverage for the new module
uv run pytest --cov=src/sleap_roots_training --cov-report=term-missing tests/
```

### Phase 6: Commit

Commit with a descriptive message linking the test and implementation:

```bash
git add src/sleap_roots_training/<module>.py tests/test_<module>.py
git commit -m "feat: Add <feature description>

- Tests define expected behavior including edge cases
- Implementation satisfies all test cases
- Known-answer fixtures verify statistical correctness"
```

## Scientific Testing Patterns

### Known-Answer Tests

For statistical functions, use hand-calculated or reference values:

```python
def test_correlation_known_answer(self):
    """Verify correlation with hand-calculated values."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    result = compute_correlation(x, y)
    # Perfect positive correlation
    np.testing.assert_allclose(result.r_value, 1.0, atol=1e-10)
    np.testing.assert_allclose(result.p_value, 0.0, atol=1e-10)
```

### Boundary Condition Tests

Test at the edges of valid input:

```python
def test_minimum_sample_size(self):
    """Test with minimum valid sample size."""
    x = np.array([1.0, 2.0, 3.0])  # n=3, minimum for correlation
    y = np.array([1.0, 2.0, 3.0])
    result = compute_correlation(x, y)
    assert result is not None

def test_below_minimum_sample_size(self):
    """Test with too few samples."""
    x = np.array([1.0, 2.0])  # n=2, too few
    y = np.array([1.0, 2.0])
    result = compute_correlation(x, y)
    assert result is None or np.isnan(result.r_value)
```

### Numerical Stability Tests

Verify calculations are stable with extreme values:

```python
def test_large_values(self):
    """Test numerical stability with large values."""
    x = np.array([1e10, 2e10, 3e10])
    y = np.array([1e10, 2e10, 3e10])
    result = compute_correlation(x, y)
    np.testing.assert_allclose(result.r_value, 1.0, atol=1e-6)

def test_near_zero_variance(self):
    """Test behavior with near-constant data."""
    x = np.array([1.0, 1.0, 1.0, 1.0001])
    y = np.array([2.0, 2.0, 2.0, 2.0001])
    result = compute_correlation(x, y)
    # Should handle gracefully, not produce NaN or crash
```

## Fixture Patterns

### Parametrized Tests

```python
@pytest.mark.parametrize("method,expected_range", [
    ("pearson", (-1, 1)),
    ("spearman", (-1, 1)),
    ("kendall", (-1, 1)),
])
def test_correlation_methods(self, sample_data, method, expected_range):
    """Test all correlation methods produce valid output."""
    result = compute_correlation(sample_data.x, sample_data.y, method=method)
    assert expected_range[0] <= result.r_value <= expected_range[1]
```

### Shared Fixtures

```python
@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    np.random.seed(42)
    n = 100
    x = np.random.randn(n)
    y = 0.5 * x + np.random.randn(n) * 0.5
    return pd.DataFrame({"x": x, "y": y})
```

## Integration

- Run `/lint` during Phase 5 to check code style
- Run `/coverage` to verify test coverage meets threshold
- Run `/run-ci-locally` before committing to ensure full CI passes
- Use `/pre-merge-check` for comprehensive PR readiness
