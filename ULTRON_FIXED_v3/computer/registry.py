from dataclasses import dataclass, field
from typing import Callable, Dict, Any


@dataclass
class Action:
    name: str
    description: str
    params: Dict[str, str] = field(default_factory=dict)
    handler: Callable[..., Any] = None
    level: int = 2
    examples: list = field(default_factory=list)


class Registry:
    def __init__(self):
        self.actions: Dict[str, Action] = {}

    def register(self, name, description, params=None, examples=None):
        def deco(fn):
            self.actions[name] = Action(name, description, params or {}, fn, examples=examples or [])
            return fn
        return deco

    def get(self, name):
        return self.actions.get(name)

    def catalog(self):
        return [{"name": a.name, "description": a.description,
                 "params": a.params, "level": a.level} for a in self.actions.values()]


REGISTRY = Registry()
