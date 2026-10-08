---
name: input-token-guard
description: Diagnose and prevent Codex input token overflow errors by estimating local content, selecting relevant excerpts, and splitting oversized inputs into safe chunks.
---

# Input Token Guard

Use this skill when Codex reports that input tokens exceed a configured limit, or before sending a very large collection of files, logs, transcripts, or generated tool output.

The error is about the full request context: the current message plus retained conversation history, system instructions, tool results, and attached content. Do not retry the same payload unchanged.

## Recovery workflow

1. Treat the reported total as an approximate hard failure boundary. Keep the next request well below the configured limit; use a working target of 750,000 estimated tokens or less unless the user gives a smaller limit.
2. If the existing thread is already huge, prepare a compact handoff and continue in a new thread. Keep only the goal, decisions, current state, relevant file paths, exact errors, and the next action.
3. Inspect local inputs before including them. Run `<plugin-root>/scripts/token_budget.py estimate` on candidate files or directories. Do not paste full generated files, dependency trees, build artifacts, binary data, or repeated tool output into the conversation.
4. Narrow the payload by relevance: search first, then read matching files and bounded excerpts. Prefer line ranges, summaries, diffs, and `head`/`tail` slices.
5. When one source is still too large, run `scripts/token_budget.py split` and process the numbered chunks one at a time. Keep chunk size comfortably below the remaining context budget; 50,000–100,000 estimated tokens per chunk is a useful default.
6. After each chunk, retain a short structured summary and discard the raw chunk from the next request. Ask for a final synthesis only after all chunks have been summarized.

## Estimation rules

`<plugin-root>/scripts/token_budget.py` provides a conservative, dependency-free estimate. It is a planning signal, not the provider's exact tokenizer. Leave headroom for instructions, tool results, and the reply. Prefer the script's reported `recommended_payload_tokens` over the configured maximum.

Examples:

```bash
python3 <plugin-root>/scripts/token_budget.py estimate README.md src/ logs/app.log
python3 <plugin-root>/scripts/token_budget.py estimate --limit 922000 .
python3 <plugin-root>/scripts/token_budget.py split huge.log --max-tokens 80000 --output-dir work/huge-log
```

For a directory, exclude generated or low-value content with `--exclude` patterns, for example `--exclude node_modules --exclude .git --exclude dist`.

## Compact handoff format

When moving to a new thread, carry a short note with these fields:

```text
Goal: <one sentence>
Current state: <what is already done>
Relevant files: <small list of absolute paths>
Evidence: <exact error or test result>
Decisions: <constraints and choices already made>
Next action: <one concrete step>
```

Never claim that the script's estimate is an exact token count, and never include secrets merely because they occur in a large input. Redact credentials and private tokens before splitting or quoting files.
