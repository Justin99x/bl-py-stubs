from .runner import register_module

CLASS_DEF_DATA_DIR = '../../sdk_mods/bl_py_stubs/class_def_data'  # Either relative to in-game SDK location or absolute path
PYSTUBS_DIR = 'data/gamestubs'  # Relative to this project
COMMON_DIR = f'{PYSTUBS_DIR}/common'
BL2_DIR = f'{PYSTUBS_DIR}/bl2'
TPS_DIR = f'{PYSTUBS_DIR}/tps'


def get_pkg_dir(base_dir: str, pkg_name: str) -> str:
    return f'{base_dir}/{pkg_name}'


def get_pkg_init(base_dir: str, pkg_name: str):
    return f'{get_pkg_dir(base_dir, pkg_name)}/__init__.pyi'

register_module(__name__)
