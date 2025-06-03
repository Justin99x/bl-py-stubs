import os
import pickle
import shutil
import textwrap

from .definitions import  ClassDef
from .paths import BL2_DIR, CLASS_DEF_DATA_DIR, COMMON_DIR, PYSTUBS_DIR, \
    TPS_DIR, get_pkg_dir, \
    get_pkg_init


def write_class_stub(base_dir: str, class_def: ClassDef) -> None:
    '''Function to write the stub file. Fields need to all be d
    efined as properties so that game specific versions can subclass them.'''
    lines = class_def.to_str()

    # Write the file
    with open(f'{get_pkg_dir(base_dir, class_def.package)}/{class_def.name()}.pyi', 'w') as f:
        f.write(lines)

    # Write import statement to __init__.pyi so that importing something like Core.Object gets the Object class and not the module
    with open(get_pkg_init(base_dir, class_def.package), 'a') as f:
        f.write(f'from .{class_def.name()} import {class_def.name()}\n')


def class_list_to_all(class_list: list[str]) -> str:
    lines = ["__all__ = ["]
    for i, item in enumerate(class_list):
        lines.append(f"    '{item}',")
    lines.append("]")
    return '\n'.join(lines)


def write_stubs(base_dir: str, class_defs: list[ClassDef]) -> None:
    packages = set([class_def.package for class_def in class_defs])

    # Clear out old stubs and add __init__.py files
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
        os.makedirs(base_dir)
    for pkg in packages:
        pkg_dir = get_pkg_dir(base_dir, pkg)
        os.makedirs(pkg_dir)
        with open(get_pkg_init(base_dir, pkg), 'w') as f:
            pass

    package_classes = {pkg: [] for pkg in packages}
    for class_def in class_defs:
        write_class_stub(base_dir, class_def)
        package_classes[class_def.package].append(class_def.name())

    for pkg in packages:
        with open(get_pkg_init(base_dir, pkg), 'a') as f:
            f.write(class_list_to_all(package_classes[pkg]))

    with open(f'{base_dir}/__init__.py', 'w') as f:
        f.writelines([f'from .{pkg} import *\n' for pkg in packages])


if __name__ == '__main__':

    with open(f'{CLASS_DEF_DATA_DIR}/common_class_defs_adj.pkl', 'rb') as f:
        common_class_defs: list[ClassDef] = pickle.load(f)

    with open(f'{CLASS_DEF_DATA_DIR}/tps_class_defs_adj.pkl', 'rb') as f:
        tps_class_defs: list[ClassDef] = pickle.load(f)

    with open(f'{CLASS_DEF_DATA_DIR}/bl2_class_defs_adj.pkl', 'rb') as f:
        bl2_class_defs: list[ClassDef] = pickle.load(f)


    write_stubs(COMMON_DIR, common_class_defs)
    write_stubs(TPS_DIR, tps_class_defs)
    write_stubs(BL2_DIR, bl2_class_defs)

    # type_defs.pyi needed as reference for OutParam and AttributeProperty
    with open(f'{PYSTUBS_DIR}/type_defs.pyi', 'w') as f:
        f.write(textwrap.dedent(
        '''\
        from typing import Generic, TypeVar

        # Create a generic Out type to indicate out parameters
        T = TypeVar('T')


        class OutParam(Generic[T]):
            """
            Indicates that a parameter is an 'out' parameter.
            """


        class AttributeProperty(Generic[T]):
            """
            Indicates that the property is an attribute property.
            """
        '''
        ))
