# MemoryOS Database

SQLite is the central local index. There is no ORM.

Database path:

```text
~/Memory/_system/database/memory.sqlite3
```

## Tables

- `notes` - canonical indexed Markdown objects.
- `projects` - project entities derived from notes.
- `people` - person entities derived from notes.
- `repositories` - repository entities derived from notes.
- `commands` - commands detected in note bodies.
- `tags` - unique tags.
- `note_tags` - many-to-many note tags.
- `links` - graph edges from one object to another target.
- `aliases` - alternate names and source paths.
- `history` - append-only action history.
- `fts_index` - SQLite FTS5 virtual table.

## Drafts

Draft memories are Markdown files under:

```text
~/Memory/_system/drafts/
```

They are intentionally excluded from `memory rebuild`, SQLite FTS, and normal context exports until promoted.

## Quality Metadata

New learned memories may include frontmatter fields:

- `quality_score`
- `outcome`
- `curator_reason`
- `repository`
- `pr_url`
- `pr_number`
- `merged_at`

Older notes without these fields remain valid.

## Identity

`notes.id` is a UUID from Markdown frontmatter. The file path is not an identifier and may change.

## Rebuild

```bash
memory rebuild
```

Rebuild reads Markdown files, refreshes entity tables, links, tags, command index, and FTS.
