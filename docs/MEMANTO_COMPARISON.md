# Memanto vs MemoryOS

Дата анализа: 2026-06-27

Источники:

- GitHub: <https://github.com/moorcheh-ai/memanto>
- README Memanto: <https://github.com/moorcheh-ai/memanto#readme>
- Memanto docs, Introduction: <https://docs.memanto.ai/getting-started/introduction>
- Memanto docs, Quickstart CLI: <https://docs.memanto.ai/getting-started/quickstart-cli>
- Memanto docs, Memory Operations: <https://docs.memanto.ai/guides/memory-operations>
- Memanto docs, On-Prem Overview: <https://docs.memanto.ai/on-prem/overview>
- Memanto docs, Integrations: <https://docs.memanto.ai/integrations/overview>
- Memanto docs, Memory Types: <https://docs.memanto.ai/reference/memory-types>

## 1. Что такое Memanto

Memanto - это готовая система долговременной памяти для AI-агентов. Ее идея: дать агентам отдельный слой памяти, к которому они могут обращаться между сессиями, вместо того чтобы каждый раз заново объяснять контекст проекта.

Memanto называет себя active memory agent. То есть это не просто база данных, куда агент кладет текст, а отдельный помощник для операций с памятью: сохранить, найти и ответить на основе памяти.

Главные операции Memanto:

- `remember` - сохранить память;
- `recall` - найти релевантную память;
- `answer` - получить ответ, основанный на найденной памяти.

## 2. Какие задачи он решает

Memanto решает задачи, похожие на верхний слой нашей MemoryOS:

- сохранять факты, решения, предпочтения, ошибки и уроки между сессиями;
- давать агентам постоянный контекст;
- искать не только по точным словам, но и по смыслу;
- разделять память по агентам и сессиям;
- подключать память к Claude Code, Cursor, Codex и другим инструментам;
- делать daily summaries, находить конфликты и противоречия;
- загружать документы в память.

Это больше похоже на готовую agent-memory платформу, чем на простую локальную Markdown-систему.

## 3. Основные команды и сценарии использования

По документации и README основные команды такие:

- `memanto` - интерактивная настройка;
- `memanto status` - состояние окружения, конфигурации, сервера, агента и сессии;
- `memanto agent create ...` - создать агента;
- `memanto agent activate ...` - активировать агента/сессию;
- `memanto remember "..." --type fact` - сохранить память;
- `memanto remember --batch memories.json` - пакетное сохранение;
- `memanto remember --from-conversation chat.json --dry-run` - извлечь память из истории диалога в preview-режиме;
- `memanto recall "..."` - смысловой поиск;
- `memanto recall "..." --type preference` - поиск с фильтром по типу;
- `memanto answer "..."` - ответ на основе памяти;
- `memanto upload file.pdf` - загрузить документ в память;
- `memanto conflicts` - найти противоречия;
- `memanto daily-summary` - дневная сводка;
- `memanto memory export` - экспорт памяти;
- `memanto memory sync` - синхронизация `MEMORY.md` в проект;
- `memanto connect codex` или похожие команды - подключение к агентским инструментам.

Типичный сценарий:

1. Установить Memanto.
2. Настроить cloud или on-prem backend.
3. Создать агента.
4. Сохранять факты через `remember`.
5. Искать через `recall`.
6. Подключить IDE/агента через `connect`.

## 4. Как он хранит и извлекает память

Memanto хранит память как typed semantic memory. У каждой memory-записи есть:

- content;
- type;
- optional title;
- optional confidence;
- optional metadata.

Типы памяти включают `fact`, `preference`, `decision`, `commitment`, `goal`, `event`, `instruction`, `relationship`, `context`, `learning`, `observation`, `error`, `artifact`.

Извлечение работает через Moorcheh - semantic engine, который Memanto описывает как information-theoretic search engine. Важная идея: память должна быть доступна для поиска сразу после записи, без долгого indexing pipeline.

В отличие от MemoryOS, Memanto делает ставку не на Markdown + SQLite + FTS5, а на semantic retrieval через Moorcheh. Markdown там есть как экспорт/sync, но не выглядит главным форматом хранения.

## 5. Внешние API, ключи, облако и локальная работа

Memanto может работать двумя путями:

- Cloud: нужен Moorcheh API key, запросы идут в Moorcheh Cloud.
- On-Prem: Memanto работает с локальным Moorcheh server в Docker; API key Moorcheh не нужен.

Для fully local/on-prem режима нужны Docker и локальный стек. В документации on-prem режим описан как вариант, где данные и embeddings остаются на своем железе. Для LLM/answer режима on-prem может использовать Ollama или собственные OpenAI/Cohere ключи, но базовый локальный путь возможен без Moorcheh Cloud.

Итог: Memanto не обязательно облачный, но он заметно тяжелее MemoryOS. Для локального режима нужны Docker/Moorcheh/Ollama-ориентированная инфраструктура, а не просто файлы + SQLite.

## 6. Что у Memanto уже лучше, чем у MemoryOS

Memanto сильнее в готовой agent-memory функциональности:

- semantic search уже является основной моделью, а не будущим расширением;
- есть typed memory с 13 категориями;
- есть agent/session модель;
- есть `remember / recall / answer` как простая mental model для агентов;
- есть integrations с Codex, Claude Code, Cursor и другими инструментами;
- есть conflict detection;
- есть daily summaries и scheduling;
- есть upload документов разных форматов;
- есть REST API, UI и TypeScript SDK;
- есть cloud/on-prem переключение одной концепцией backend;
- есть зрелая упаковка как внешний инструмент.

Если нам нужна готовая универсальная память для многих AI-инструментов прямо сейчас, Memanto функционально шире.

## 7. Что у MemoryOS лучше или ближе к нашим задачам

MemoryOS лучше подходит к нашей конкретной цели:

- вся память остается человекочитаемой в Markdown;
- SQLite лежит локально и прозрачно;
- нет обязательного Docker, backend server, API key или внешнего semantic engine;
- структура папок понятна и живет годами без приложения;
- `memory learn --from-session` уже собирает инженерный опыт именно после задач агента;
- Codex workflow уже встроен через `AGENTS.md`;
- архитектура проще и легче переносится на Mac/homelab;
- можно открыть заметку обычным редактором и понять, что произошло;
- меньше зависимостей и меньше скрытого поведения.

Главное отличие: MemoryOS строится как личная файловая система инженерной памяти, а Memanto - как готовая agent-memory платформа.

## 8. Есть ли смысл интегрировать Memanto сейчас

Сейчас прямую интеграцию делать не стоит.

Причины:

- наша MemoryOS еще формирует собственную модель данных;
- у нас уже есть локальная цепочка `learn --from-session`;
- Memanto добавит Docker/Moorcheh/backend complexity;
- semantic memory может быть полезной позже, но сейчас главный риск - преждевременно усложнить систему;
- мы не хотим превращать Markdown-first MemoryOS в зависимость от внешнего retrieval engine.

Memanto стоит оставить как источник идей и как потенциальный optional backend в будущем.

## 9. Что можно позаимствовать без прямой интеграции

Полезные идеи для MemoryOS:

1. Три простые операции: `remember`, `recall`, `answer`.
   У нас уже есть `add/search/context`, но можно добавить alias-команды или UX-слой:
   - `memory remember`;
   - `memory recall`;
   - `memory answer` позже.

2. Typed memory taxonomy.
   У нас уже есть типы объектов, но можно сблизить их с практичными типами:
   - `fact`;
   - `preference`;
   - `decision`;
   - `learning`;
   - `error`;
   - `artifact`;
   - `instruction`.

3. Confidence и provenance.
   MemoryOS стоит добавить поля:
   - `confidence`;
   - `evidence`;
   - `observed_by`;
   - `source_file`;
   - `source_command`.

4. Conflict detection.
   Полезная будущая команда:
   - `memory conflicts`
   - сначала простая: искать противоречивые решения/дубли/устаревшие заметки.

5. Daily workflow.
   У нас есть `digest`; можно развить:
   - daily summary;
   - weekly summary;
   - review inbox;
   - stale decisions.

6. Export/sync в проектный `MEMORY.md`.
   Это хорошо совпадает с нашей идеей `AGENTS.md` и context export.

7. Agent/session модель.
   У нас уже есть session notes. Можно добавить явные поля:
   - `agent`;
   - `session_id`;
   - `task_id`;
   - `tool`;
   - `duration`.

8. `--from-conversation --dry-run`.
   У нас есть `learn --from-session --dry-run`. Позже можно добавить:
   - `memory learn --from-transcript transcript.json --dry-run`.

## 10. Риски

### Приватность

Cloud-режим Memanto требует Moorcheh API key и отправляет память в внешний сервис. Для личных, рабочих и медицинских данных это не подходит по умолчанию.

On-prem режим лучше, но все равно требует внимательно понимать, где лежат данные, embeddings, uploads и LLM-провайдер.

### Сложность

MemoryOS сейчас легкая: Markdown, SQLite, Python. Memanto добавляет Docker, Moorcheh server, backend switching, sessions, tokens, server/UI/API.

Это полезно для платформы, но тяжеловато для нашего текущего локального MVP.

### Зависимость от внешнего сервиса

Даже если Memanto open source, его поиск завязан на Moorcheh SDK/engine. Если мы встроим его глубоко, MemoryOS перестанет быть простой SQLite-first системой.

### Переносимость

MemoryOS можно перенести как папку Markdown + SQLite. Memanto on-prem переносим, но вместе с сервисами, контейнерами и конфигурацией.

### Расхождение целей

Memanto оптимизирован как универсальная agent-memory система. MemoryOS оптимизирована под нашу инженерную память: задачи, команды, ошибки, решения, контекст проектов и автоматический learn после задач.

## 11. Итоговая рекомендация

Рекомендация: не интегрировать Memanto сейчас, но внимательно заимствовать идеи.

Выбор из вариантов:

- Копировать подход: частично, на уровне UX и типов памяти.
- Интегрировать: не сейчас.
- Не трогать: не совсем; как источник идей он полезен.
- Вернуться позже: да, после стабилизации MemoryOS.

Практический план:

1. Оставить MemoryOS основной системой.
2. Не добавлять Memanto как зависимость сейчас.
3. Заимствовать typed memory, confidence/provenance, conflict detection, daily workflow, `remember/recall/answer` UX.
4. Вернуться к Memanto позже как к optional semantic backend или мосту для внешних агентов.

## Главный ответ

Memanto - не замена MemoryOS.

Для нас Memanto сейчас скорее источник идей и возможный будущий optional backend. Он сильнее как готовая semantic memory платформа для многих AI-агентов, но MemoryOS лучше совпадает с нашей целью: независимая локальная, простая, человекочитаемая инженерная память на Markdown и SQLite, построенная вокруг ежедневной работы с OpenAI Codex.

## Короткий вывод для пользователя

Memanto выглядит сильным и зрелым инструментом для памяти AI-агентов.
Но он решает задачу как отдельная платформа с semantic backend, Docker/on-prem или cloud.
Наша MemoryOS проще, прозрачнее и лучше подходит под личную инженерную память на Mac.
Сейчас Memanto не стоит интегрировать напрямую.
Лучше взять идеи: типы памяти, `remember/recall/answer`, confidence, provenance, conflicts и daily summaries.
Вернуться к интеграции стоит позже, когда MemoryOS стабилизируется и понадобится semantic backend.
