import importlib
from pathlib import Path
from .base import BaseSprayModule

module_dir = Path(__file__).parent
module_choices = {}

for file in module_dir.glob("*.py"):
    file = module_dir / file

    if file.is_file() and file.stem not in ["base", "__init__"]:
        modules = importlib.import_module(
            f"trevorspray.lib.sprayers.{file.stem}", "trevorspray"
        )

        for m in modules.__dict__.keys():
            module = getattr(modules, m)
            try:
                if BaseSprayModule in module.__mro__:
                    module_choices[file.stem] = module
            except AttributeError:
                continue
