from typing import cast

from src.runner import register_module
from src.definitions import ClassDef, EnumDef, FunctionDef, ParamRef, PropertyRef, ReturnRef, StructDef,  TypeCat, TypeRef
from src.game import Game, GAME

from unrealsdk import find_all
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


def get_property_ref(prop: UProperty) -> PropertyRef:
    if prop.Class.Name == 'ArrayProperty':
        type_ref = get_property_ref(prop.Inner).type_ref
        type_ref.type_constructors += ['list']
    elif prop.Class.Name == 'StructProperty':
        type_ref = TypeRef.from_uobject(prop.Struct)
    elif prop.Class.Name in ['ObjectProperty', 'ComponentProperty']:
        type_ref = TypeRef.from_uobject(prop.PropertyClass)
    elif prop.Class.Name == 'ByteProperty' and prop.Enum:
        type_ref = TypeRef.from_uobject(prop.Enum)
    elif prop.Class.Name == 'InterfaceProperty':
        type_ref = TypeRef.from_uobject(prop.InterfaceClass)
    elif prop.Class.Name == 'ClassProperty':
        type_ref = TypeRef.from_uobject(prop.MetaClass)
        type_ref.type_constructors = ['type']
    elif prop.Class.Name == 'DelegateProperty':
        type_ref = TypeRef.from_uobject(prop.Signature)
    elif prop.Class.Name == 'Const':
        type_ref = TypeRef(names=['str'], package='BUILTIN', type_cat=TypeCat.CONST, game=Game.COMMON)
    elif prop.Class.Name in BASIC_TYPES.keys():
        type_ref = TypeRef(names=[BASIC_TYPES[prop.Class.Name]], package='BUILTIN', type_cat=TypeCat.BUILTIN, game=Game.COMMON)
    elif prop.Class.Name in ATTRIBUTE_TYPES.keys():
        type_ref = TypeRef(names=[ATTRIBUTE_TYPES[prop.Class.Name]], package='BUILTIN', type_cat=TypeCat.BUILTIN, game=Game.COMMON)
        type_ref.type_constructors = ['AttributeProperty']
    else:
        info(prop.Name)
        info(prop.Class.Name)
        info(prop.__class__)
        raise Exception()


    if hasattr(prop, "ArrayDim") and prop.ArrayDim > 1:
        type_ref.type_constructors += [f'tuple_{prop.ArrayDim}']


    return PropertyRef(var_name=prop.Name, type_ref=type_ref)


def get_function_def(func: UFunction) -> FunctionDef:
    func_type = FunctionDef.from_uobject(func)
    prop = func.Children
    while prop:
        flags = parse_property_flags(prop.PropertyFlags)
        if 'Parm' in flags:  # Only want parameters
            prop_ref = get_property_ref(cast(UProperty, prop))
            if 'ReturnParm' in flags:
                return_ref = ReturnRef(type_ref=prop_ref.type_ref)
                func_type.ret = return_ref
            else:
                param_ref = ParamRef(var_name=prop.Name, type_ref=prop_ref.type_ref)
                # Adjust for out and optional params
                if 'OutParm' in flags:
                    param_ref.type_ref.type_constructors.append('Out')
                if 'OptionalParm' in flags:
                    param_ref.type_ref.type_constructors.append('Optional')
                func_type.params.append(param_ref)
        prop = prop.Next
    if not func_type.ret:
        func_type.ret = ReturnRef(TypeRef(['None'], 'BUILTIN', TypeCat.BUILTIN, Game.COMMON, []))
    return func_type


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

    enum_type = EnumDef.from_uobject(enum)
    enum_type.attributes = values
    return enum_type


def get_struct_def(struct: UStruct) -> StructDef:
    struct_type = StructDef.from_uobject(struct)

    if struct.SuperField:
        struct_type.supers = [TypeRef.from_uobject(struct.SuperField)]

    prop: UField | None = struct.Children  # Linked list
    while prop:
        struct_type.properties.append(get_property_ref(cast(UProperty, prop)))
        prop = prop.Next

    return struct_type


def get_class_def(cls: UClass) -> ClassDef:
    class_def = ClassDef.from_uobject(cls)
    class_def.game = GAME
    if cls.SuperField:
        cls_super = TypeRef.from_uobject(cls.SuperField)
        cls_super.game = GAME
        class_def.supers = [cls_super]

    prop: UField | None = cls.Children  # Linked list
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
            class_def.properties.append(get_property_ref(cast(UProperty, prop)))

        prop = prop.Next

    return class_def


def get_class_defs():
    classes = find_all('Class')

    class_defs = []
    for cls in classes:
        # if cls.Name in ('WillowPawn', 'Object'):
        class_defs.append(get_class_def(cast(UClass, cls)))

    return class_defs




register_module(__name__)