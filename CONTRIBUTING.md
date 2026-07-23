# Contributing

Thanks for helping improve MemoryOS.

## Before Opening A Change

1. Search existing issues first.
2. Keep the change focused on one user-visible problem.
3. Do not add personal memory folders, SQLite files, logs, exports, pending records, or secrets to Git.
4. Preserve Markdown frontmatter IDs when editing sample or fixture notes.

## Local Checks

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/memoryos-pycache python -m compileall memoryos
git diff --check
```

## Pull Requests

Describe the user problem, the behavioral change, and the checks you ran. Add or update focused tests when behavior changes. Keep Markdown notes human-readable and prefer the standard library unless a dependency is clearly necessary.
