---
id: "8f5d9b08-6501-4a3f-8279-1d44c87b9c4e"
title: "Example decision: keep Markdown as durable storage"
type: "decision"
project: "example-project"
status: "completed"
tags: ["example", "architecture"]
created: "2026-07-23 12:00"
updated: "2026-07-23 12:00"
source: "example"
parent: ""
related: []
aliases: []
---

# Decision

Keep Markdown files as the durable record and use SQLite only as a derived local search index.

## Why

- Notes remain readable and portable without the index.
- `memory rebuild` can restore search from the Markdown source.
- The storage model stays local-first and simple to inspect.
