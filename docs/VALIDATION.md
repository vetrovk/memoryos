# Validation Program

MemoryOS can collect local, metadata-only snapshots for a time-bounded validation
program. The workflow is opt-in and lazy: it has no LaunchAgent, cron job,
daemon, network access, learning action, or automatic `memory used` call.

An active program is described by `<memory-home>/_system/validation/program.json`:

```json
{
  "schema_version": 1,
  "active": true,
  "started_at": "2026-08-07T00:00:00+00:00",
  "ends_at": "2026-09-07T23:59:59+00:00",
  "snapshot_interval_days": 7,
  "last_snapshot_at": "2026-08-07T00:00:00+00:00"
}
```

When any regular MemoryOS CLI command runs, it first reads this small file. If
the program is active, within its date range, and the interval has elapsed, it
writes one snapshot to `<memory-home>/_system/validation/`. Otherwise the CLI
continues without a snapshot. A short local lock prevents concurrent commands
from producing multiple snapshots for the same interval.

Snapshots contain aggregate usage statistics, Curator action counts, limited
Curator metadata and reason codes, and index counts. They do not contain note
bodies, queries, note titles, `memory used` reasons, or quarantined content.
The workflow remains observational: a found result is not treated as proof that
memory improved an engineering decision.
