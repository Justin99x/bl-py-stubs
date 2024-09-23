import os
import shutil
from copy import copy
from dataclasses import dataclass, field
from typing import List, Optional, Set, cast

from unrealsdk import find_all, find_object
from unrealsdk.logging import info
from unrealsdk.unreal import UClass, UEnum, UField, UFunction, UProperty, UStruct

# Define the EPropertyFlags as constants
CPF_Parm = 0x80  # Function parameter
CPF_ConstParm = 0x200  # Constant function parameter
CPF_OutParm = 0x100  # Output parameter
CPF_OptionalParm = 0x10  # Optional parameter
CPF_ReturnParm = 0x400  # Return value parameter

# Dictionary mapping each flag to its name
property_flags_dict = {
    CPF_Parm: "Parm",
    CPF_ConstParm: "ConstParm",
    CPF_OutParm: "OutParm",
    CPF_OptionalParm: "OptionalParm",
    CPF_ReturnParm: "ReturnParm"
}


# Function to parse the property flags
def parse_property_flags(flags):
    if not flags:
        return ["None"]
    result = []
    for flag, description in property_flags_dict.items():
        if flags & flag:
            result.append(description)
    return result if result else ["None"]


BASIC_TYPES = {
    'BoolProperty': 'bool',
    'ByteProperty': 'int',
    'Const': 'Final[Any]',
    'FloatProperty': 'float',
    'IntProperty': 'int',
    'NameProperty': 'str',
    'StrProperty': 'str',
    'MapProperty': 'dict',
}

ATTRIBUTE_TYPES = {
    'FloatAttributeProperty': 'float',
    'IntAttributeProperty': 'int',
    'ByteAttributeProperty': 'int',
}

IGNORE_PROPERTIES = (
    'State',
)

DEFAULT_IMPORTS = [
    'from type_defs import Out, AttributeProperty\n',
    'from typing import Final, Any, Optional, Type, Callable\n'
    'from enum import IntEnum\n'
    '\n'
]


@dataclass
class PropertyData:
    import_str: str
    type: str


@dataclass(frozen=True)
class DependencyDef:
    module: str
    name: str


@dataclass
class PropertyDef:
    prop_type: str
    var_name: Optional[str]
    dependency: DependencyDef


@dataclass
class FunctionDef:
    name: str
    params: List[PropertyDef] = field(default_factory=list)
    ret: Optional[PropertyDef] = None
    dependencies: Set[DependencyDef] = field(default_factory=set)


@dataclass
class EnumDef:
    name: str = ''
    attributes: dict = field(default_factory=dict)


@dataclass
class StructDef:
    name: str
    super: Optional[PropertyDef]
    properties: List[PropertyDef] = field(default_factory=list)
    dependencies: Set[DependencyDef] = field(default_factory=set)


@dataclass
class ClassDef(StructDef):
    functions: List[FunctionDef] = field(default_factory=list)
    structs: List[StructDef] = field(default_factory=list)
    enums: List[EnumDef] = field(default_factory=list)


def get_property_def(prop: UProperty) -> PropertyDef:
    if prop.Class.Name == 'ArrayProperty':
        inner = get_property_def(prop.Inner)
        return PropertyDef(f'list[{inner.prop_type}]', prop.Name, inner.dependency)

    elif prop.Class.Name == 'StructProperty':
        prop_type = prop.Struct.Name
        prop_path = prop.Struct.Outer._path_name()
    elif prop.Class.Name in ['ObjectProperty', 'ComponentProperty']:
        prop_type = prop.PropertyClass.Name
        prop_path = prop.PropertyClass.Outer._path_name()
    elif prop.Class.Name == 'ByteProperty' and prop.Enum:
        prop_type = prop.Enum.Name
        prop_path = prop.Enum.Outer._path_name()
    elif prop.Class.Name == 'InterfaceProperty':
        prop_type = prop.InterfaceClass.Name
        prop_path = prop.InterfaceClass.Outer._path_name()
    elif prop.Class.Name == 'ClassProperty':
        prop_type = f'Type[Any]'
        prop_path = None
    elif prop.Class.Name == 'DelegateProperty':
        prop_type = 'Callable'
        prop_path = None
    elif prop.Class.Name in BASIC_TYPES.keys():
        prop_type = BASIC_TYPES.get(prop.Class.Name)
        prop_path = None
    elif prop.Class.Name in ATTRIBUTE_TYPES.keys():
        prop_type = f'AttributeProperty[{ATTRIBUTE_TYPES.get(prop.Class.Name)}]'
        prop_path = None
    else:
        info(prop.Name)
        info(prop.Class.Name)
        info(prop.__class__)
        prop_type = ''
        prop_path = ''

    return PropertyDef(prop_type, prop.name, DependencyDef(prop_path, prop_type))


def get_function_def(func: UFunction) -> FunctionDef:
    func_def = FunctionDef(func.Name)
    prop = func.Children
    while prop:
        flags = parse_property_flags(prop.PropertyFlags)
        if 'Parm' in flags:  # Only want parameters
            property_def = get_property_def(cast(UProperty, prop))
            if 'ReturnParm' in flags:
                func_def.ret = property_def
            else:
                # Adjust prop type for out and optional params
                if 'OutParm' in flags:
                    property_def.prop_type = f'Out[{property_def.prop_type}]'
                if 'OptionalParm' in flags:
                    property_def.prop_type = f'Optional[{property_def.prop_type}] = None'
                func_def.params.append(property_def)
            func_def.dependencies.add(property_def.dependency)
        prop = prop.Next

    return func_def


def get_enum_def(enum: UEnum) -> EnumDef:
    # Logic taken from Apple's Enum library
    values = {}
    idx = 0
    while True:
        val_name = enum.GetEnum(enum, idx)
        if val_name == "None":
            break
        values[val_name] = idx
        idx += 1

    return EnumDef(enum.Name, values)


def get_struct_def(struct: UStruct) -> StructDef:
    if struct.SuperField:
        super = PropertyDef(struct.SuperField.Name, None, DependencyDef(struct.SuperField.Outer._path_name(), struct.SuperField.Name))
    else:
        super = None
    struct_def = StructDef(struct.Name, super)
    prop: UField = struct.Children  # Linked list
    while prop:
        struct_def.properties.append(get_property_def(cast(UProperty, prop)))
        prop = prop.Next

    for prop in struct_def.properties:
        struct_def.dependencies.add(prop.dependency)
    return struct_def


def get_class_def(cls: UStruct) -> ClassDef:
    if cls.SuperField:
        super = PropertyDef(cls.SuperField.Name, None, DependencyDef(cls.SuperField.Outer._path_name(), cls.SuperField.Name))
    else:
        super = None
    class_def = ClassDef(cls.Name, super)

    prop: UField = cls.Children  # Linked list
    while prop:
        if prop.Class.Name == 'ScriptStruct':
            class_def.structs.append(get_struct_def(cast(UStruct, prop)))
        elif prop.Class.Name == 'Enum':
            class_def.enums.append(get_enum_def(cast(UEnum, prop)))
        elif prop.Class.Name == 'Function':
            class_def.functions.append(get_function_def(cast(UFunction, prop)))
        elif prop.Class.Name in IGNORE_PROPERTIES:
            pass
        else:
            class_def.properties.append(get_property_def(cast(UProperty, prop)))

        prop = prop.Next

    if super:
        class_def.dependencies.add(super.dependency)
    for prop in class_def.properties:
        class_def.dependencies.add(prop.dependency)
    for func in class_def.functions:
        class_def.dependencies.update(func.dependencies)
    for struct in class_def.structs:
        class_def.dependencies.update(struct.dependencies)

    return class_def


def get_pkg_dir(pkg_name: str) -> str:
    return f'../../sdk_mods/bl_py_stubs/pystubs/{pkg_name}'


def get_pkg_init(pkg_name: str):
    return f'{get_pkg_dir(pkg_name)}/__init__.pyi'


def make_class_stub(cls: UClass) -> None:
    class_def = get_class_def(cls)
    lines = copy(DEFAULT_IMPORTS)

    # Write dependencies as import statements
    for dependency in class_def.dependencies:
        if dependency.module and dependency.module != cls._path_name() and dependency.name != cls.Name:
            lines.append(f'from {dependency.module} import {dependency.name}\n')

    # Define enums as IntEnum
    for enum in class_def.enums:
        lines.append(f'\n\nclass {enum.name}(IntEnum):\n')
        for attr, val in enum.attributes.items():
            lines.append(f'\t{attr} = {val}\n')

    # Define structs as classes. Since it's just stubs we don't need something fancy like a dataclass
    for struct in class_def.structs:
        lines.append(f'\n\nclass {struct.name}({struct.super.prop_type if struct.super else ""}):\n')
        for property in struct.properties:
            lines.append(f'\t{property.var_name}: {property.prop_type}\n')

    # Define the main class
    lines.append(f'\n\nclass {class_def.name}({class_def.super.prop_type if class_def.super else ""}):\n')
    # Add all the properties of the class
    for property in class_def.properties:
        lines.append(f'\t{property.var_name}: {property.prop_type}\n')

    # Add all the class functions
    for func in class_def.functions:
        param_defs = ', '.join([f'{param.var_name}: {param.prop_type}' for param in func.params])
        lines.append(f'\tdef {func.name}(self{", " + param_defs if param_defs else ""}) -> {func.ret.prop_type if func.ret else "None"}: ...\n')

    # If class def is empty, add a pass statement
    if (not class_def.properties) and (not class_def.functions):
        lines.append(f'\tpass')

    # Write the file
    with open(f'{get_pkg_dir(cls.Outer.Name)}/{cls.Name}.pyi', 'w') as f:
        f.writelines(lines)

    # Write import statement to __init__.pyi so that importing something like Core.Object gets the Object class and not the module
    with open(get_pkg_init(cls.Outer.Name), 'a') as f:
        f.write(f'from .{cls.Name} import {cls.Name}\n')


def class_list_to_all(class_list: List[str]) -> str:
    lines = [f"__all__ = ["]
    for i, item in enumerate(class_list):
        lines.append(f"    '{item}',")
    lines.append("]")
    return '\n'.join(lines)


def main():
    classes = find_all('Class')

    packages = set([cls.Outer.Name for cls in classes])
    package_classes = {pkg: [] for pkg in packages}

    for pkg in packages:
        dir = get_pkg_dir(pkg)
        if os.path.exists(dir):
            shutil.rmtree(dir)
        os.makedirs(dir)
        with open(get_pkg_init(pkg), 'w') as f:
            pass

    for cls in classes:
        make_class_stub(cls)
        package_classes[cls.Outer.Name].append(cls.Name)

    for pkg in packages:
        with open(get_pkg_init(pkg), 'a') as f:
            f.write(class_list_to_all(package_classes[pkg]))


main()
# cls = find_object('Class', 'WillowGame.WillowInventoryManager')
# class_def = get_class_def(cls)
