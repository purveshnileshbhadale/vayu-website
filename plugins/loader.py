import importlib
import inspect
import sys
from pathlib import Path


class Plugin:
    def __init__(self, name: str, description: str, params: dict, handler):
        self.name = name
        self.description = description
        self.params = params
        self.handler = handler


_plugins: dict[str, Plugin] = {}
_loaded = False


def _plugin_dir() -> Path:
    return Path(__file__).resolve().parent


def load_plugins():
    global _loaded
    if _loaded:
        return
    _loaded = True

    pd = _plugin_dir()
    for f in sorted(pd.glob("*.py")):
        if f.name in ("__init__.py", "loader.py"):
            continue

        mod_name = f"plugins.{f.stem}"
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
        else:
            try:
                spec = importlib.util.spec_from_file_location(mod_name, f)
                if not spec or not spec.loader:
                    continue
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
            except Exception as e:
                print(f"[Plugins] Failed to load {f.name}: {e}")
                continue

        if not hasattr(mod, "register"):
            continue

        try:
            result = mod.register()
            if isinstance(result, dict):
                result = [result]
            for entry in result:
                p = Plugin(
                    name=entry["name"],
                    description=entry["description"],
                    params=entry.get("parameters", {}),
                    handler=entry["handler"],
                )
                _plugins[p.name] = p
                print(f"[Plugins] Registered: {p.name}")
        except Exception as e:
            print(f"[Plugins] register() failed in {f.name}: {e}")


def get_plugin(name: str) -> Plugin | None:
    return _plugins.get(name)


def get_all_plugins() -> list[Plugin]:
    return list(_plugins.values())


def plugin_declarations() -> list[dict]:
    return [
        {
            "name": p.name,
            "description": p.description,
            "parameters": {
                "type": "OBJECT",
                "properties": p.params,
            },
        }
        for p in _plugins.values()
    ]


def execute_plugin(name: str, args: dict, player=None) -> str:
    p = _plugins.get(name)
    if not p:
        return f"Plugin not found: {name}"
    try:
        return p.handler(args, player=player) or "Done."
    except Exception as e:
        return f"Plugin '{name}' failed: {e}"
