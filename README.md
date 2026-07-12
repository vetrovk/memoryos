# MemoryOS

Локальная персональная система памяти для человека и AI-агентов: Markdown-объекты, UUID, SQLite-индекс, FTS5-поиск, связи, история, Python API и CLI.

По умолчанию данные создаются в `~/Memory`. Код скриптов лежит отдельно в этом репозитории.

## What Is MemoryOS?

MemoryOS is a local-first memory engine for humans and AI agents. It stores durable notes as Markdown, indexes them with SQLite FTS5, and exposes both a Python API and CLI.

The repository contains only the engine. Your personal memory folder, SQLite database, logs, exports, drafts, cache, health notes, work notes, and secrets must stay outside Git.

## Структура памяти

- `00_inbox/` - входящие заметки без сортировки
- `10_projects/` - проекты
- `20_people/` - люди, контакты, роли
- `30_company/` - рабочие знания по компании
- `40_health/` - личные медицинские заметки
- `50_ai/` - AI, Codex, агенты, промпты
- `60_guides/` - инструкции, команды, чек-листы
- `70_decisions/` - принятые решения
- `80_errors/` - ошибки и способы исправления
- `90_archive/` - архив
- `_system/database/` - SQLite
- `_system/config/` - конфигурация
- `_system/logs/` - логи
- `_system/exports/` - контекстные экспорты
- `_system/plugins/` - будущие плагины
- `_system/scripts/` - служебные скрипты
- `_system/cache/` - локальный кэш
- `_system/drafts/` - черновики памяти, которые пока не попали в постоянную память

## Быстрый старт

Без установки пакета:

```bash
python3 -m memoryos.cli init
python3 -m memoryos.cli add --title "Oracle Bot заметка" --type project --project oracle --tags "oracle,bot" --text "Краткий контекст проекта."
python3 -m memoryos.cli rebuild
python3 -m memoryos.cli search "oracle bot"
python3 -m memoryos.cli context oracle
python3 -m memoryos.cli learn --project oracle --goal "Завершить настройку индекса" --action "Добавлен CLI learn" --command-used "python3 -m memoryos.cli doctor"
python3 -m memoryos.cli drafts
python3 -m memoryos.cli github-pr https://github.com/owner/repo/pull/123
python3 -m memoryos.cli digest
python3 -m memoryos.cli doctor
```

Editable install:

```bash
python3 -m pip install -e .
memory init
memory doctor
```

После установки в editable-режиме будет доступна команда `memory`:

```bash
python3 -m pip install -e .
memory init
memory search "oracle bot"
```

Также работают Makefile-обертки:

```bash
make init
make add TITLE="Oracle Bot заметка" TYPE=project PROJECT=oracle TAGS="oracle,bot" TEXT="Краткий контекст проекта."
make index
make search QUERY="oracle bot"
make context PROJECT=oracle
make learn PROJECT=oracle GOAL="Завершить задачу" TAGS="codex,session"
make learn-session PROJECT=oracle SOURCE=codex ACTOR=codex
make drafts
make github-pr PR_URL=https://github.com/owner/repo/pull/123
make digest
make doctor
```

Если нужно тестировать без записи в `~/Memory`:

```bash
make init MEMORY_HOME=/tmp/memory-test
make search MEMORY_HOME=/tmp/memory-test QUERY="oracle"
```

## Do Not Commit Personal Memory

Before publishing or pushing a fork, check:

```bash
git status --short
find . \( -name '*.sqlite3' -o -name '*.db' -o -name '*.log' -o -name '.env' \) -print
```

Never commit:

- `~/Memory`
- `Memory/`
- `_system/`
- SQLite databases
- logs
- drafts
- exports
- cache
- `.env`
- tokens or API keys
- health, work, or personal notes

## Добавление заметки

```bash
memory add --title "Название" --type decision --project oracle --tags "архитектура,sqlite" --text "Решение и причина."
```

Доступные типы: `project`, `person`, `company`, `guide`, `decision`, `error`, `command`, `session`, `prompt`, `idea`, `health_note`, `architecture`, `repository`, `github_pr_learning`, `project_note`.

Каждая заметка получает YAML frontmatter:

```yaml
---
id: "uuid"
title: "..."
type: "project"
project: "oracle"
status: "active"
tags: ["oracle", "bot"]
created: "YYYY-MM-DD HH:MM"
updated: "YYYY-MM-DD HH:MM"
source: "manual"
parent: ""
related: []
aliases: []
---
```

## Поиск

```bash
memory search "oracle bot"
memory search --project oracle
memory search --type decision
memory search --tags "sqlite,архитектура"
```

Поиск использует локальный SQLite FTS5 с `unicode61`, поэтому кириллица индексируется без внешних сервисов.

## Индексация

```bash
memory rebuild
```

Команда перечитывает Markdown-файлы и пересобирает индекс. Ошибки отдельных файлов пишутся в `~/Memory/_system/logs/memory.log`.

## Экспорт контекста для Codex

```bash
memory context oracle
```

Экспорт создается в `~/Memory/_system/exports/context_oracle_<date>.md` и включает описание проекта, архитектуру, решения, ошибки, команды, roadmap, репозитории и связи.

## Импорт проекта

```bash
memory import ~/Projects/OmniBot --project omnibot
```

Импорт читает Markdown и распространенные проектные файлы: `README.md`, `CHANGELOG.md`, `TODO.md`, `AGENTS.md`, `Makefile`, `requirements.txt`, `pyproject.toml`, `Dockerfile`.

## Автоматическое обучение памяти

### Activity log vs real memory

MemoryOS больше не должна сохранять каждую активность как постоянную память. Не каждая сессия достойна долгого хранения. Постоянная память должна хранить решения, ошибки, выводы, PR, review, merge и полезный инженерный опыт.

`memory learn --from-session` теперь проходит через простой Memory Curator:

- считает `quality_score`;
- определяет `outcome`;
- пропускает пустые сессии;
- снижает score для временных проектов вроде `tmp` и runtime/plugin папок;
- ищет дубликаты по проекту, changed files hash, commit и похожей цели;
- сохраняет сильные записи в постоянную память;
- слабые записи сохраняет в `_system/drafts/` или пропускает с понятным сообщением.

### Generated Files Are Activity Noise, Not Engineering Memory

Перед scoring curator исключает generated/dependency пути: `node_modules/`, `dist/`, `build/`, `out/`, `.next/`, `.nuxt/`, cache/temporary folders, virtualenvs, bytecode, логи, `.DS_Store` и common minified bundles. Они не попадают в заметку, aliases, links, diff summary и fingerprint.

Настройки можно переопределить локально в `~/Memory/_system/config/curator.json`; пример лежит в [examples/curator.json](examples/curator.json). `.github/` не исключается по умолчанию, поскольку CI/workflow изменения могут быть важной инженерной работой.

Самый короткий путь для агента после завершения задачи:

```bash
python3 -m memoryos.cli learn --from-session --actor codex --source codex
```

Предварительный просмотр без сохранения:

```bash
python3 -m memoryos.cli learn --from-session --actor codex --source codex --dry-run
```

Можно переопределить проект:

```bash
python3 -m memoryos.cli learn --from-session --project memoryos --actor codex --source codex
```

`--from-session` автоматически собирает текущий проект, `git status`, `git diff --stat`, измененные файлы, последний commit, безопасные git-команды, краткие выводы и рекомендации. Внешние API и LLM не используются.

Черновики:

```bash
memory drafts
memory drafts review
memory drafts promote <id>
memory drafts drop <id>
memory curator-stats --days 7
memory cleanup-generated --dry-run
```

Curator audit хранится в SQLite `history`: saved, draft, skipped, promote и drop решения записываются вместе с причиной, score и raw/useful/ignored file counts.

После успешного завершения задачи агент может сохранить структурированную запись:

```bash
python3 -m memoryos.cli learn \
  --project oracle \
  --goal "Исправить поиск по проекту" \
  --action "Добавлен SearchProvider" \
  --file "memoryos/search.py" \
  --decision "Оставить SQLite FTS5 как MVP-поиск" \
  --command-used "python3 -m memoryos.cli doctor" \
  --finding "Индекс обновляется сразу после сохранения" \
  --recommendation "Позже добавить vector provider"
```

Для агентов удобнее JSON:

```bash
python3 -m memoryos.cli learn --from-json task-learning.json
```

Минимальная схема JSON:

```json
{
  "project": "oracle",
  "goal": "Исправить поиск по проекту",
  "actions": ["Добавлен SearchProvider"],
  "changed_files": ["memoryos/search.py"],
  "errors": [],
  "decisions": ["Оставить SQLite FTS5 как MVP-поиск"],
  "commands": ["python3 -m memoryos.cli doctor"],
  "findings": ["Индекс обновляется сразу после сохранения"],
  "recommendations": ["Позже добавить vector provider"],
  "tags": ["codex", "task-learning"],
  "source": "codex",
  "actor": "codex"
}
```

`memory learn` сохраняет запись как объект `session`, добавляет UUID frontmatter, индексирует ее в SQLite, извлекает команды в `commands`, связывает измененные файлы через `links` и aliases.

## GitHub PR memory

PR можно сохранить как инженерную память:

```bash
memory learn --from-github-pr https://github.com/owner/repo/pull/123
memory github-pr https://github.com/owner/repo/pull/123
```

MVP использует GitHub CLI `gh`, если он установлен. Если `gh` недоступен или не может прочитать PR, команда честно пишет причину и не создает запись.

Новая заметка получает тип `github_pr_learning` и содержит ссылку на PR, репозиторий, номер, автора, reviewers, review/comments, outcome, связанные файлы, issues и выводы.

## Диагностика

```bash
make doctor
```

Проверяет папки, SQLite, FTS5, UUID в Markdown, битые Markdown-файлы и дубликаты заголовков.

## Ежедневная автоматическая индексация

Файл launchd подготовлен в `launchd/com.local.memory.index.plist`. Перед включением замените путь к репозиторию, если он отличается.

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.local.memory.index.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.local.memory.index.plist
```

Автозапуск не включается автоматически. Сначала проверьте `make index` и `make doctor`.

## Будущие расширения

- векторный поиск рядом с FTS5;
- импорт из GitHub и логов проектов;
- Obsidian-совместимость;
- локальный веб-интерфейс;
- синхронизация на homelab;
- дайджесты по отдельным проектам.
