# Contributing to CodeNavigator

Thank you for your interest in CodeNavigator. This document explains how to contribute to the project in an open-source setting, with expectations suited to use by Talan teams.

## Purpose

CodeNavigator is a code exploration, documentation generation, and RAG tool. Contributions are welcome as long as they remain consistent with the existing architecture, code readability, and project maintainability.

## Table of Contents

- [Before You Start](#before-you-start)
- [Naming and Working Conventions](#naming-and-working-conventions)
  - [Branches](#branches)
  - [Issues](#issues)
  - [Commits](#commits)
- [Checks Before Submitting a Contribution](#checks-before-submitting-a-contribution)
- [Code Conventions](#code-conventions)
- [Tests](#tests)

## Before You Start

1. Read the [README](README.md) to understand the features, prerequisites, and main commands.
2. Review and agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). We maintain a respectful and inclusive community.
3. Check that no existing issue or discussion already covers the topic.
4. Work on a dedicated branch created from `dev`.

## Naming and Working Conventions

To keep the history readable and make reviews easier, please follow these conventions.

### Branches

- Prefer short, explicit branch names such as `feat/add-docs-export`, `fix/chat-reset`, or `docs/contributing-update`.
- Avoid vague names such as `patch`, `update`, or `test`.
- If possible, tie the branch name to the issue topic.
- Always create your branch from `dev` following the `<type>/<short-description>#<issueID>` naming convention, for example `feat/add-login#7` or `docs/update-readme#15`. This aligns with Conventional Commits and improves project consistency.

```bash
git checkout dev
git pull origin dev
git checkout -b feat/my-feature dev
```

### Issues

- Describe the business or technical need in one clear sentence.
- Add context, the expected outcome, and, if useful, reproduction steps.
- Provide acceptance criteria when the topic is not purely technical.
- Use a short, action-oriented title that makes the topic easy to understand at a glance.

### Commits

This repository follows the Conventional Commits convention.

Recommended format:

```text
<type>(<scope>): <short description>
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`, `perf`, `ci`.

Examples:

- `feat(graph): add module dependency export`
- `fix(chat): handle empty conversation history`
- `docs(contributing): add contribution rules`

Keep commit messages short, precise, and consistent with the actual content of the commit.

## Checks Before Submitting a Contribution

Before opening a pull request, run at least the checks relevant to your change.

### Python Tests

In this workspace, the reference command is:

```powershell
CodeNavigator-Explore-understand-and-document-code/.venv/Scripts/python.exe -m pytest -q
```

### Frontend

If your change affects the UI or React components, run the frontend tests and TypeScript checks according to the scripts defined in `frontend/package.json`.

### Quality

- Make sure the code remains consistent with the project style.
- Keep changes focused and limited to the functional need.
- Add or update tests when behavior changes.

## Code Conventions

### Python

- Use `snake_case` for functions and variables.
- Use `PascalCase` for classes and Pydantic models.
- Add type annotations to public signatures.
- Prefer `logging` over `print()`.
- Keep FastAPI routes explicit with `response_model` and `status_code`.
- Do not return raw dictionaries when a model exists.

### React / TypeScript

- Use functional components.
- Prefer named exports except for pages.
- Avoid `any` without a clear justification.
- Follow the existing structure of `frontend/src`.

## Tests

The project follows a test approach close to the modified module.

- Backend Python: `pytest`
- FastAPI API: integration tests with `httpx` and `AsyncClient`
- Frontend: `@testing-library/react`

When you add a feature, aim for at least one happy path and one error case when it makes sense.

## Contribution Flow

1. Open an issue or clearly describe the need before coding if the change is significant.
2. Implement the change on a dedicated branch.
3. Add or update the tests.
4. Verify the result locally.
5. Open a pull request with a clear description of the problem, the solution, and the validations performed.

## Pull Request Best Practices

- A PR should ideally cover a single topic.
- Describe the business context if the change touches code exploration, generation, or RAG.
- List the test commands you ran.
- Include screenshots or output excerpts if the UI or docs change.

## Security and Secrets

Never commit secrets, API keys, or sensitive data. If a contribution requires a new configuration, document it in the README or in the appropriate configuration files.

## Questions and Support

If you are contributing on behalf of a Talan team, mention the usage context in the pull request to help with review and prioritization.

For a question, please specify as much as possible:

- the functional or business context,
- the file or module involved,
- what has already been tried,
- the error output or observed behavior,
- whether the question concerns architecture, packaging, tests, or deployment.

The more precise the question, the easier it is to answer quickly and usefully.
