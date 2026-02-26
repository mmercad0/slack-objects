# Copilot Instructions

## Project Guidelines
- Follow Unix philosophy: build small, composable functions where higher-level methods leverage lower-level primitives. Don't mix concerns (e.g., don't embed identifier resolution inside a SCIM CRUD method). Keep signatures consistent across sibling methods.
- Prefer consistency with the `Users.is_active`/`is_active_scim` pattern when structuring related methods (separate explicit SCIM method from higher-level orchestration).