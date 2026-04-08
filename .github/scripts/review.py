"""
review.py

Shared review logic for both pipelines.
Called by GitHub Actions with environment variables.

Environment variables:
    MISTRAL_API_KEY     — Mistral API key
    GITHUB_TOKEN        — GitHub token with pull-requests: write
    GITHUB_REPOSITORY   — e.g. "owner/repo"
    PR_NUMBER           — pull request number
    PR_TITLE            — pull request title
    PR_BODY             — pull request description
    COMMIT_SHA          — latest commit SHA on the PR branch
    PIPELINE_MODE       — "inline" (level 1) or "comment" (level 2)
    DIFF_TRUNCATED      — "true" if diff was truncated
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
COMMIT_SHA = os.environ["COMMIT_SHA"]
PIPELINE_MODE = os.environ.get("PIPELINE_MODE", "comment")  # "inline" | "comment"
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


def parse_unified_diff(diff_text: str):
    """
    Returns position_map: dict[(file, new_line_no)] -> diff_position
    Position resets per file as required by GitHub Review API.
    """
    position_map = {}
    current_file = None
    diff_position = 0
    new_line_no = 0
    old_line_no = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            diff_position = 0
            current_file = None
            continue

        if line.startswith("--- "):
            continue

        if line.startswith("+++ "):
            match = re.match(r"^\+\+\+ b/(.+)$", line)
            if match:
                current_file = match.group(1)
                diff_position = 0
            continue

        if line.startswith("@@"):
            match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if match and current_file:
                old_line_no = int(match.group(1))
                new_line_no = int(match.group(2))
                diff_position += 1
            continue

        if current_file is None:
            continue

        if line.startswith("+"):
            diff_position += 1
            position_map[(current_file, new_line_no)] = diff_position
            new_line_no += 1
        elif line.startswith("-"):
            diff_position += 1
            old_line_no += 1
        else:
            diff_position += 1
            position_map[(current_file, new_line_no)] = diff_position
            new_line_no += 1
            old_line_no += 1

    return position_map


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

## Conventions — Python / FastAPI
- snake_case functions/variables, PascalCase classes and Pydantic models
- SCREAMING_SNAKE_CASE constants
- Type hints on every function signature
- Pydantic models for all request/response bodies — never raw dicts
- logging only, never print()
- Black (88 chars), isort
- All routes: explicit response_model, explicit status_code, async for I/O
- Depends() for shared logic (auth, db session)
- Background work returns 202
- Concurrent access to shared state must be under a lock
- Read-modify-write on files must be atomic (single lock covering read + write)

## Conventions — React / TypeScript
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
# LLM call — inline mode (structured JSON output)
# ---------------------------------------------------------------------------

INLINE_USER_PROMPT_TEMPLATE = """
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
      "line": <int — new file line number, must exist in the diff>,
      "comment": "<direct description of the issue and why it matters>",
      "suggestion": "<replacement code block if applicable, else null>"
    }}
  ],
  "suggestions": [
    {{
      "file": "<path/to/file.py>",
      "line": <int — new file line number, must exist in the diff>,
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
# LLM call — comment mode (markdown output)
# ---------------------------------------------------------------------------

COMMENT_USER_PROMPT_TEMPLATE = """
PR Title: {title}
PR Description: {body}

Commits:
{commits}

Diff:
{diff}
{truncation_note}

Respond with a structured review in this exact format:

## Review Summary
Score: X/10
Verdict: APPROVE | REQUEST_CHANGES | NEEDS_DISCUSSION

---

## Blocking Issues
- [file:line] Description and why it matters. Concrete fix if applicable.

## Suggestions
- [file:line] Non-blocking improvement.

## Commit Messages
- List commits not following Conventional Commits, or "All commits follow the convention."

## Notes
General observations (scope, size, suggest splitting if >400 lines changed).

Rules:
- Be direct. No preamble, no closing summary.
- If no blocking issues, write "No blocking issues."
- If no suggestions, omit that section.
"""

# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def delete_previous_bot_comment(marker: str):
    """Deletes the previous AI review comment if it exists."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/{PR_NUMBER}/comments"
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    for comment in resp.json():
        if comment.get("body", "").startswith(marker):
            del_url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/comments/{comment['id']}"
            requests.delete(del_url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
            print(f"Deleted previous comment {comment['id']}")
            break


def post_pr_comment(body: str):
    """Posts a general PR comment."""
    marker = "## AI Code Review"
    delete_previous_bot_comment(marker)
    url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/{PR_NUMBER}/comments"
    resp = requests.post(
        url,
        headers=HEADERS,
        json={"body": body},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    print(f"Posted PR comment: {resp.json()['id']}")


def post_review_with_inline_comments(review_data: dict, position_map: dict):
    """
    Posts a GitHub Pull Request Review with inline comments.
    Falls back to a PR comment if no valid positions are found.
    """
    score = review_data.get("score", 0)
    verdict_map = {
        "APPROVE": "APPROVE",
        "REQUEST_CHANGES": "REQUEST_CHANGES",
        "NEEDS_DISCUSSION": "COMMENT",
    }
    gh_event = verdict_map.get(review_data.get("verdict", "COMMENT"), "COMMENT")

    # Build review body (summary)
    body_lines = [
        "## AI Code Review (Mistral)",
        "",
        f"**Score**: {score}/10 — **{review_data.get('verdict', 'N/A')}**",
        "",
        review_data.get("summary", ""),
    ]

    if review_data.get("commit_violations"):
        body_lines += ["", "### Commit Convention Violations"]
        for v in review_data["commit_violations"]:
            body_lines.append(f"- {v}")

    if review_data.get("notes"):
        body_lines += ["", "### Notes", review_data["notes"]]

    review_body = "\n".join(body_lines)

    # Build inline comments
    comments = []
    unresolved = []  # items that could not be mapped to a diff position

    all_items = [
        ("blocking", item) for item in review_data.get("blocking_issues", [])
    ] + [("suggestion", item) for item in review_data.get("suggestions", [])]

    for kind, item in all_items:
        file = item.get("file", "")
        line = item.get("line")
        comment_text = item.get("comment", "")
        suggestion = item.get("suggestion")

        if not file or not line:
            unresolved.append(item)
            continue

        position = position_map.get((file, int(line)))
        if position is None:
            # Line not in diff — try adjacent lines (+/- 3)
            for delta in range(1, 4):
                position = position_map.get((file, int(line) + delta))
                if position:
                    break
                position = position_map.get((file, int(line) - delta))
                if position:
                    break

        if position is None:
            unresolved.append(item)
            continue

        prefix = "**[BLOCKING]** " if kind == "blocking" else ""
        body = f"{prefix}{comment_text}"
        if suggestion:
            body += f"\n\n{suggestion}"

        comments.append(
            {
                "path": file,
                "position": position,
                "body": body,
            }
        )

    # Append unresolved items to the review body
    if unresolved:
        review_body += (
            "\n\n### Additional findings (could not be anchored to a diff line)\n"
        )
        for item in unresolved:
            review_body += f"\n- **{item.get('file', '?')}:{item.get('line', '?')}** — {item.get('comment', '')}"
            if item.get("suggestion"):
                review_body += f"\n{item['suggestion']}"

    # Dismiss previous reviews from this bot
    _dismiss_previous_reviews()

    # Post the review
    url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/pulls/{PR_NUMBER}/reviews"
    payload = {
        "commit_id": COMMIT_SHA,
        "body": review_body,
        "event": gh_event,
        "comments": comments,
    }

    resp = requests.post(
        url,
        headers=HEADERS,
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not resp.ok:
        print(f"GitHub API error {resp.status_code}: {resp.text}", file=sys.stderr)

        # GitHub Actions tokens may be forbidden from APPROVE/REQUEST_CHANGES.
        # Fallback to a neutral COMMENT review to avoid failing the workflow.
        if resp.status_code == 422 and payload.get("event") != "COMMENT":
            payload["event"] = "COMMENT"
            resp_comment = requests.post(
                url,
                headers=HEADERS,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if resp_comment.ok:
                print(
                    f"Posted COMMENT review fallback with {len(comments)} inline comments: "
                    f"{resp_comment.json()['id']}"
                )
                return
            print(
                f"GitHub API fallback error {resp_comment.status_code}: {resp_comment.text}",
                file=sys.stderr,
            )

        # Fallback: post without inline comments
        payload["comments"] = []
        payload["event"] = "COMMENT"
        resp2 = requests.post(
            url,
            headers=HEADERS,
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp2.raise_for_status()
        print(f"Posted review without inline comments (fallback): {resp2.json()['id']}")
    else:
        print(
            f"Posted review with {len(comments)} inline comments: {resp.json()['id']}"
        )


def _dismiss_previous_reviews():
    """Dismisses previous REQUEST_CHANGES reviews from GITHUB_TOKEN user to avoid blocking merges."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/pulls/{PR_NUMBER}/reviews"
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    if not resp.ok:
        return
    for review in resp.json():
        if review.get("state") == "REQUEST_CHANGES" and review.get(
            "body", ""
        ).startswith("## AI Code Review"):
            dismiss_url = f"{url}/{review['id']}/dismissals"
            requests.put(
                dismiss_url,
                headers=HEADERS,
                json={"message": "Superseded by new review."},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )


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

    if PIPELINE_MODE == "inline":
        annotated_diff = build_annotated_diff(diff_text)
        position_map = parse_unified_diff(diff_text)

        user_prompt = INLINE_USER_PROMPT_TEMPLATE.format(
            title=PR_TITLE,
            body=PR_BODY,
            commits=commits,
            diff=annotated_diff,
            truncation_note=truncation_note,
        )

        print("Calling Mistral (inline mode)...")
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
            # Fallback to comment mode
            post_pr_comment(
                f"## AI Code Review\n\nCould not parse structured review. Raw output:\n\n{raw}"
            )
            sys.exit(0)

        post_review_with_inline_comments(review_data, position_map)

    else:  # comment mode
        user_prompt = COMMENT_USER_PROMPT_TEMPLATE.format(
            title=PR_TITLE,
            body=PR_BODY,
            commits=commits,
            diff=diff_text,
            truncation_note=truncation_note,
        )

        print("Calling Mistral (comment mode)...")
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=4096,
            temperature=0.1,
        )

        review_text = response.choices[0].message.content
        post_pr_comment(f"## AI Code Review\n\n{review_text}")


if __name__ == "__main__":
    main()
