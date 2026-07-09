# MemoryOS Plugin API

Plugins are intentionally minimal in the MVP.

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

## Planned Plugins

- GitHub
- Obsidian
- Telegram
- RSS
- Filesystem
- Log Parser
- Session Importer

The first included plugin is `FilesystemPlugin`, used as a simple importer wrapper around `memory.import_path()`.
