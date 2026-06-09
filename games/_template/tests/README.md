# Game Tests

Each game directory contains its own Python test suite under `tests/`:

```
tests/
  __init__.py
  test_engine.py       # Game engine and logic tests
  test_metrics.py      # Game-specific metrics tests
```

## Frontend UI Tests

Frontend UI contract tests live in the frontend project under
`frontend/src/__tests__/games/<game>-ui.test.tsx`.

These tests verify that the game's `ui/LiveView.tsx` and `ui/ConfigForm.tsx`
components render correctly with the shared component library and app
context providers. Each new game should have a corresponding test file
that imports its UI components via the `@games` path alias.

The tests intentionally live inside the frontend project (not here)
because Vitest's Vite integration requires test files to be within the
project root to resolve `node_modules` dependencies.
