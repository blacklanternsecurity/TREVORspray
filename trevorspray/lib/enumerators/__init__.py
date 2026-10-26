import importlib
from pathlib import Path
from .base import Enumerator

module_dir = Path(__file__).parent
module_choices = {}

# Then scan for any additional modules
for file in module_dir.glob("*.py"):
    if file.is_file() and file.stem not in ["base", "__init__"]:
        modules = importlib.import_module(
            f"trevorspray.lib.enumerators.{file.stem}", "trevorspray"
        )

        for m in modules.__dict__.keys():
            module = getattr(modules, m)
            try:
                if Enumerator in module.__mro__ and m not in module_choices:
                    module_choices[file.stem] = module
            except AttributeError:
                continue
