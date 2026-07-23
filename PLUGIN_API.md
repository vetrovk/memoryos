# MemoryOS Extension Boundary

MemoryOS currently exposes a small experimental extension boundary for future importers and automations. It is not a dynamic plugin system and does not define a stable third-party plugin compatibility API.

The codebase exports `BasePlugin` and ships one concrete implementation, `FilesystemPlugin`. `FilesystemPlugin` is a thin wrapper around `memory.import_path()`; the CLI does not discover or load plugins automatically.

```python
from memoryos.plugins import BasePlugin


class MyPlugin(BasePlugin):
    name = "my_plugin"

    def run(self, **kwargs):
        return {"ok": True}
```

`BasePlugin` receives a `Memory` instance:

```python
plugin = MyPlugin(memory)
plugin.run()
```

There is currently no plugin registry, configuration-driven loading, Python entry-point loading, external package registration, or compatibility commitment for third-party plugins. Treat this boundary as an internal, beta-level extension point that may change before v1.0.
