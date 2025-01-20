
import argparse
import copy
import importlib
import pickle
import sys
from collections import defaultdict

import_order = defaultdict(list)
def register_module(module_name):
    base_module = module_name.split('.')[0]
    if module_name not in import_order[base_module]:
        import_order[base_module].append(module_name)


try:
    from mods_base import command, Game as mods_base_Game

    @command
    def bps(args: argparse.Namespace) -> None:
        """Utility to automatically reload modules in the correct order. Requires that they all implement register_module"""
        from .game_class_defs import get_class_defs
        from .paths import CLASS_DEF_DATA_DIR

        module = 'src'
        import_order_copy = copy.copy(import_order[module])
        import_order[module] = []
        for module_name in import_order_copy:
            module = sys.modules.get(module_name)
            if module:
                importlib.reload(module)
                print(f'Reloaded module {module_name}')


        class_defs = get_class_defs()
        game_str = mods_base_Game.get_current().name

        with open(f'{CLASS_DEF_DATA_DIR}/{game_str}_class_defs.pkl', 'wb') as f:
            pickle.dump(class_defs, f)


except ImportError:
    pass