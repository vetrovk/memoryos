PYTHON ?= python3
MEMORY_HOME ?= $(HOME)/Memory
MEMORY ?= $(PYTHON) -m memoryos.cli
TITLE ?= Untitled note
TYPE ?=
PROJECT ?=
TAGS ?=
TEXT ?=
SOURCE ?= manual
STATUS ?= active
QUERY ?=
IMPORT_PATH ?= .
GOAL ?=
ACTOR ?= agent
LEARN_JSON ?= task-learning.json
PR_URL ?=
DAYS ?= 7

.PHONY: init add import import-pending learn learn-json learn-session drafts curator-stats cleanup-generated index rebuild search digest doctor context stats graph github-pr agents

init:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) init

add:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) add --title "$(TITLE)" --type "$(if $(TYPE),$(TYPE),idea)" --project "$(PROJECT)" --tags "$(TAGS)" --text "$(TEXT)" --source "$(SOURCE)" --status "$(STATUS)"

import:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) import "$(IMPORT_PATH)" --project "$(PROJECT)"

import-pending:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) import-pending --days "$(DAYS)"

learn:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) learn --project "$(PROJECT)" --goal "$(GOAL)" --tags "$(TAGS)" --source "$(SOURCE)" --actor "$(ACTOR)"

learn-json:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) learn --from-json "$(LEARN_JSON)"

learn-session:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) learn --from-session --project "$(PROJECT)" --source "$(SOURCE)" --actor "$(ACTOR)"

drafts:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) drafts

curator-stats:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) curator-stats --days "$(DAYS)"

cleanup-generated:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) cleanup-generated --dry-run

github-pr:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) github-pr "$(PR_URL)" --source "$(SOURCE)" --actor "$(ACTOR)"

index:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) rebuild

rebuild:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) rebuild

search:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) search --query "$(QUERY)" --project "$(PROJECT)" --tags "$(TAGS)" --type "$(TYPE)"

digest:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) digest

doctor:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) doctor

context:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) context "$(PROJECT)"

stats:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) stats

graph:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) graph

agents:
	MEMORY_HOME="$(MEMORY_HOME)" $(MEMORY) agents "$(PROJECT)"
