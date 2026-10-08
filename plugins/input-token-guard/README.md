# Input Token Guard

Input Token Guard is a local Codex plugin for diagnosing and preventing errors such as:

> `400 - upstream: Input tokens exceed the configured limit of 922000 tokens`

It adds a Codex skill plus a dependency-free Python helper that can:

- estimate the token footprint of files, directories, or standard input;
- reserve headroom below a configured provider limit;
- exclude generated directories such as `.git`, `node_modules`, `dist`, and `build`;
- split oversized text files into numbered chunks with a manifest;
- guide a compact handoff into a new Codex thread when retained history is already too large.

The estimator is deliberately conservative. It is a planning signal, not the provider's exact tokenizer.

## Usage from the installed plugin

Resolve the plugin root and run the helper:

```bash
python3 <plugin-root>/scripts/token_budget.py estimate --limit 922000 /path/to/files
python3 <plugin-root>/scripts/token_budget.py split /path/to/large.log --max-tokens 80000 --output-dir ./work/token-chunks
```

For local development from this repository:

```bash
python3 plugins/input-token-guard/scripts/token_budget.py estimate --limit 922000 plugins/input-token-guard
```

## Privacy and safety

The helper reads local files only to estimate or split the text you explicitly select. Redact credentials and private tokens before sending chunks to any model provider.
