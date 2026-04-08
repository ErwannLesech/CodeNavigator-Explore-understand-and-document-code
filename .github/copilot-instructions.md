# Copilot Instructions

## Project Overview

This project is an AI-powered SDLC automation tool. It takes a raw text input
(bug report, feature request) and runs it through a LangGraph pipeline that
generates structured user stories, Jira tickets, and GitHub issues.

Stack:
- Backend: FastAPI + Python 3.11, LangGraph, Mistral API
- Frontend: React + TypeScript
- Package layout: src/ai_agentic_sdlc/ (core, pipeline, integrations)
- Entry points: main.py (CLI), backend/app.py (FastAPI server)

---

## Repository Structure

```
src/ai_agentic_sdlc/
  core/           # Shared models, parser, validation logic
  pipeline/       # LangGraph graph, agents, state, prompts
  integrations/   # Jira and GitHub clients

backend/
  app.py          # FastAPI bootstrap (create_app)
  routes.py       # All API route definitions
  services.py     # Business logic called by routes
  runtime.py      # Pipeline runtime state and locking
  storage.py      # JSON file persistence helpers
  schemas.py      # Request/response Pydantic models
  config.py       # Constants and file paths

frontend/
  src/            # React app source code
  public/         # Static assets

tests/            # pytest, one file per module tested
main.py           # CLI entry point
```

---

## Conventions

### Python
- `snake_case` for functions and variables
- `PascalCase` for classes and Pydantic models
- `SCREAMING_SNAKE_CASE` for constants
- Type hints on every function signature — no exceptions
- Pydantic models for all API request/response bodies — never raw dicts
- `logging` module only, never `print()`
- Black formatting (88 char line length), isort for imports
- PEP 8 strictly

### React / TypeScript
- `PascalCase` for components, `camelCase` for hooks prefixed with `use`
- Named exports everywhere except page-level components
- No inline styles — Tailwind only
- No `any` in TypeScript without an explanatory comment
- Functional components only — no class components
- Destructure props explicitly — avoid spreading `{...props}` without reason

---

## Patterns

### FastAPI routes
Always use `response_model`, explicit `status_code`, and `async` for I/O routes.
Use `Depends()` for auth and db session injection. Never return raw dicts.
Background work returns `202 Accepted`.

### LangGraph nodes
Each node function must have the signature:
```python
def node_name(state: PipelineState) -> dict
```
Return only the keys that changed. Do not mutate state in place.

### Pydantic models
Define in `src/ai_agentic_sdlc/core/models.py` for shared models.
Route-specific request/response schemas go in `backend/schemas.py`.

### Error handling
Raise `HTTPException` with explicit status codes in routes.
Use `ValueError` / `RuntimeError` in service layer — never `HTTPException` outside routes.

### Concurrency / locking
Any access to shared mutable state (`PIPELINE_RUNTIME`, file-backed stores) must
be wrapped in `RUNTIME_LOCK`. Read-modify-write on JSON files must be atomic
(single lock acquisition covering read + write).

---

## Never do this

- Never use `print()` — use `logging`
- Never return raw dicts from FastAPI route handlers
- Never hardcode secrets, model names, or file paths — use `config.py` or env vars
- Never write class-based React components
- Never use enzyme in tests — use `@testing-library/react`
- Never import from `backend/` inside `src/ai_agentic_sdlc/` (one-way dependency)
- Never add a dependency not already in `requirements.txt` without flagging it explicitly
- Never disable a lint rule without a justification comment

---

## Testing

### Python
- New endpoints must have at least one integration test using `pytest` + `httpx` via `AsyncClient`
- Business logic in services must have unit tests
- Use fixtures for test data — no hardcoded values in test bodies
- Cover happy path + at least one error case per function
- Mock all external calls (Mistral API, Jira, GitHub) — no real network calls in CI

### React
- All new components must have at least one render test minimum
- User interaction logic must be covered (clicks, form submissions)
- Use `@testing-library/react`
- Mock API calls and auth in tests

---

## Commit Convention (Conventional Commits)

All commits must follow:
```
<type>(<scope>): <short description>
```

Valid types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`, `style`, `perf`, `ci`

Examples:
- `feat(auth): add JWT refresh token endpoint`
- `fix(pipeline): handle empty input before graph execution`
- `test(parser): add coverage for frontmatter edge cases`

---

## Copilot Behaviour

### Response style
- Be direct. No preamble, no summary at the end restating what was done.
- If a question has a one-line answer, give a one-line answer.
- Do not add explanatory comments on obvious code.

### Code changes
- Change the minimum amount of code necessary to satisfy the request.
- Do not reformat code that is not related to the change.
- Do not rename variables or restructure logic unless explicitly asked.
- If the existing code has a style inconsistency, ignore it unless fixing it
  is the task.

### Comments in code
- Do not add inline comments on self-explanatory code.
- Add a comment on any section that involves concurrency, locking, or shared
  mutable state.
- Add a comment on any non-obvious algorithmic choice or workaround.
- Add a `# TODO` comment if a known limitation is left intentionally unresolved.

### When generating new code
- Follow the existing patterns in the file — do not introduce new patterns
  without being asked.
- If two approaches are valid, pick the one already used elsewhere in the codebase.
- Never add dependencies that are not already in `requirements.txt` without
  flagging it explicitly.

### When uncertain
- If the intent of a request is ambiguous, state the assumption made before
  generating code.
- If a change would have side effects outside the current file, flag them
  explicitly before proceeding.

---

## Copilot Chat — Workflows

### Adding a FastAPI endpoint
1. Define the Pydantic request/response models in `backend/schemas.py`
2. Add the business logic in `backend/services.py`
3. Wire the route in `backend/routes.py` with `response_model` and `status_code`
4. Suggest a pytest test using `AsyncClient`

### Adding a LangGraph node
1. Add the node function in `src/ai_agentic_sdlc/pipeline/agents.py`
2. Register it in the graph in `pipeline/graph.py`
3. If it needs a prompt, add it to `pipeline/prompts.py`

### Adding a React component
1. Create the file in the appropriate feature folder, named `ComponentName.tsx`
2. Use a named export
3. Add a test file `ComponentName.test.tsx` alongside it

### Writing tests
Always use fixtures — never hardcode test data inline.
Mock external dependencies at the boundary (HTTP client, env vars).