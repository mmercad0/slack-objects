# Copilot Instructions

## Project Guidelines
- Follow Unix philosophy: build small, composable functions where higher-level methods leverage lower-level primitives. Don't mix concerns (e.g., don't embed identifier resolution inside a SCIM CRUD method). Keep signatures consistent across sibling methods.
- Prefer consistency with the `Users.is_active`/`is_active_scim` pattern when structuring related methods (separate explicit SCIM method from higher-level orchestration).

## Testing Guidelines
- Unit test files in `tests/UnitTests` must follow the naming convention `*_unit_test.py` (not `test_*` prefix). The following files should adhere to this convention: `users_unit_test.py`, `conversations_unit_test.py`, `messages_unit_test.py`, `files_unit_test.py`, `workspaces_unit_test.py`, `idp_groups_unit_test.py`, `config_unit_test.py`, and two others with the `_unit_test.py` suffix.