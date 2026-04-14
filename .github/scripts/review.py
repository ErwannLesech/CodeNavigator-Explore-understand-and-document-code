"""
review.py

Shared PR review logic.
Called by GitHub Actions with environment variables.

Environment variables:
    MISTRAL_API_KEY     - Mistral API key
    GITHUB_TOKEN        - GitHub token with pull-requests: write
    GITHUB_REPOSITORY   - e.g. "owner/repo"
    PR_NUMBER           - pull request number
    PR_TITLE            - pull request title
    PR_BODY             - pull request description
    DIFF_TRUNCATED      - "true" if diff was truncated
"""

import json
import os
import re
import sys

import requests

try:
    # mistralai>=2 exposes Mistral under mistralai.client
    from mistralai.client import Mistral
except ImportError:
    # Backward compatibility for older SDK versions
    from mistralai import Mistral

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
PR_NUMBER = os.environ["PR_NUMBER"]
PR_TITLE = os.environ.get("PR_TITLE", "")
PR_BODY = os.environ.get("PR_BODY", "")
DIFF_TRUNCATED = os.environ.get("DIFF_TRUNCATED", "false") == "true"

GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 15
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ---------------------------------------------------------------------------
# Diff parser (inline copy to keep the Action self-contained)
# ---------------------------------------------------------------------------


def build_annotated_diff(diff_text: str) -> str:
    """Annotates the diff with line numbers for LLM context."""
    parts = []
    current_file = None
    new_line_no = 0
    old_line_no = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            current_file = None
            continue
        if line.startswith("--- "):
            continue
        if line.startswith("+++ "):
            match = re.match(r"^\+\+\+ b/(.+)$", line)
            if match:
                current_file = match.group(1)
                parts.append(f"\n### FILE: {current_file}")
            continue
        if line.startswith("@@"):
            match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match:
                old_line_no = int(match.group(1))
                new_line_no = int(match.group(2))
            parts.append(line)
            continue
        if current_file is None:
            continue
        if line.startswith("+"):
            parts.append(f"+ LINE {new_line_no:4d} | {line[1:]}")
            new_line_no += 1
        elif line.startswith("-"):
            parts.append(f"- LINE {old_line_no:4d} | {line[1:]}")
            old_line_no += 1
        else:
            content = line[1:] if line.startswith(" ") else line
            parts.append(f"  LINE {new_line_no:4d} | {content}")
            new_line_no += 1
            old_line_no += 1

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a senior fullstack engineer reviewing pull requests on a project using
React (frontend) and FastAPI + Python (backend).

## Conventions ÔÇö Python / FastAPI
- snake_case functions/variables, PascalCase classes and Pydantic models
- SCREAMING_SNAKE_CASE constants
- Type hints on every function signature
- Pydantic models for all request/response bodies ÔÇö never raw dicts
- logging only, never print()
- Black (88 chars), isort
- All routes: explicit response_model, explicit status_code, async for I/O
- Depends() for shared logic (auth, db session)
- Background work returns 202
- Concurrent access to shared state must be under a lock
- Read-modify-write on files must be atomic (single lock covering read + write)

## Conventions ÔÇö React / TypeScript
- PascalCase components, camelCase hooks prefixed with use
- Named exports except page components
- No inline styles, no class components
- No any without explanatory comment

## Testing
- New endpoints: integration test with AsyncClient
- Services: unit tests
- New React components: at least one render test
- Use fixtures, no hardcoded test data
- Mock all external calls

## Commit Convention
Conventional Commits: <type>(<scope>): <description>
Valid types: feat fix chore refactor test docs style perf ci
"""

# ---------------------------------------------------------------------------
# LLM call ÔÇö pr-review mode (structured JSON output)
# ---------------------------------------------------------------------------

PR_REVIEW_USER_PROMPT_TEMPLATE = """
PR Title: {title}
PR Description: {body}

Commits:
{commits}

Diff (line numbers are annotated as LINE N):
{diff}
{truncation_note}

Respond ONLY with a valid JSON object. No markdown fences, no preamble.
Schema:
{{
  "score": <int 0-10>,
  "verdict": "APPROVE" | "REQUEST_CHANGES" | "NEEDS_DISCUSSION",
  "summary": "<2-3 sentence overall assessment>",
  "blocking_issues": [
    {{
      "file": "<path/to/file.py>",
      "line": <int ÔÇö new file line number, must exist in the diff>,
      "comment": "<direct description of the issue and why it matters>",
      "suggestion": "<replacement code block if applicable, else null>"
    }}
  ],
  "suggestions": [
    {{
      "file": "<path/to/file.py>",
      "line": <int ÔÇö new file line number, must exist in the diff>,
      "comment": "<non-blocking improvement>",
      "suggestion": "<replacement code block if applicable, else null>"
    }}
  ],
  "commit_violations": [
    "<commit message that does not follow Conventional Commits>"
  ],
  "notes": "<general observations: PR size, scope clarity, split suggestion if >400 lines>"
}}

Rules:
- file and line must refer to lines that appear in the diff (LINE N annotations).
- Do not invent line numbers that are not in the diff.
- If no blocking issues exist, set blocking_issues to [].
- If no suggestions, set suggestions to [].
- suggestion field: provide only the replacement lines (no surrounding context).
  Use GitHub suggestion block format:
  ```suggestion
  <replacement code>
  ```
  Set to null if no code replacement is applicable.
- Be direct. No vague feedback.
"""

# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def delete_previous_bot_comment(marker: str):
    """Returns the previous AI review comment id if it exists."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/{PR_NUMBER}/comments"
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    for comment in resp.json():
        if comment.get("body", "").startswith(marker):
            return comment["id"]
    return None


def post_pr_comment(body: str):
    """Creates or updates the single AI PR comment."""
    marker = "## AI Code Review"
    existing_comment_id = delete_previous_bot_comment(marker)

    if existing_comment_id:
        url = (
            f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/comments/"
            f"{existing_comment_id}"
        )
        resp = requests.patch(
            url,
            headers=HEADERS,
            json={"body": body},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        print(f"Updated PR comment: {existing_comment_id}")
        return

    url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/{PR_NUMBER}/comments"
    resp = requests.post(
        url,
        headers=HEADERS,
        json={"body": body},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    print(f"Posted PR comment: {resp.json()['id']}")


def format_structured_review_as_comment(review_data: dict) -> str:
    """Converts structured JSON review into markdown PR comment."""
    score = review_data.get("score", 0)
    verdict = review_data.get("verdict", "N/A")
    summary = review_data.get("summary", "")

    lines = [
        "## Review Summary",
        f"Score: {score}/10",
        f"Verdict: {verdict}",
    ]

    if summary:
        lines += ["", summary]

    lines += ["", "---", "", "## Blocking Issues"]

    blocking_issues = review_data.get("blocking_issues", [])
    if blocking_issues:
        for item in blocking_issues:
            lines.append(
                f"- [{item.get('file', '?')}:{item.get('line', '?')}] "
                f"{item.get('comment', '').strip()}"
            )
            if item.get("suggestion"):
                lines.append("")
                lines.append(str(item["suggestion"]))
    else:
        lines.append("No blocking issues.")

    suggestions = review_data.get("suggestions", [])
    if suggestions:
        lines += ["", "## Suggestions"]
        for item in suggestions:
            lines.append(
                f"- [{item.get('file', '?')}:{item.get('line', '?')}] "
                f"{item.get('comment', '').strip()}"
            )
            if item.get("suggestion"):
                lines.append("")
                lines.append(str(item["suggestion"]))

    lines += ["", "## Commit Messages"]
    commit_violations = review_data.get("commit_violations", [])
    if commit_violations:
        for item in commit_violations:
            lines.append(f"- {item}")
    else:
        lines.append("- All commits follow the convention.")

    lines += ["", "## Notes"]
    lines.append(review_data.get("notes", ""))

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    with open("diff.txt", "r", encoding="utf-8", errors="replace") as f:
        diff_text = f.read()

    with open("commits.txt", "r", encoding="utf-8", errors="replace") as f:
        commits = f.read()

    truncation_note = (
        "\n\n> **Note**: Diff was truncated to 3000 lines. Review may be partial.\n"
        if DIFF_TRUNCATED
        else ""
    )

    client = Mistral(api_key=MISTRAL_API_KEY)

    annotated_diff = build_annotated_diff(diff_text)

    user_prompt = PR_REVIEW_USER_PROMPT_TEMPLATE.format(
        title=PR_TITLE,
        body=PR_BODY,
        commits=commits,
        diff=annotated_diff,
        truncation_note=truncation_note,
    )

    print("Calling Mistral (pr-review mode)...")
    response = client.chat.complete(
        model="mistral-large-latest",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4096,
        temperature=0.1,
    )

    raw = response.choices[0].message.content
    print("Raw LLM response:", raw[:500])

    # Strip markdown fences if model ignored instructions
    clean = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    clean = re.sub(r"\s*```$", "", clean)

    try:
        review_data = json.loads(clean)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}\nRaw: {raw}", file=sys.stderr)
        post_pr_comment(
            f"## AI Code Review\n\nCould not parse structured review. Raw output:\n\n{raw}"
        )
        sys.exit(0)

    review_text = format_structured_review_as_comment(review_data)
    post_pr_comment(f"## AI Code Review\n\n{review_text}")


if __name__ == "__main__":
    main()
