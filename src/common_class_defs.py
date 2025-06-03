import pickle

from .definitions import ClassDef, EnumDef, StructDef
from .game import Game
from .paths import CLASS_DEF_DATA_DIR


def get_common_elements(bl2_list: list, tps_list: list) -> list:
    ret_list = []
    for element in bl2_list + tps_list:
        if element in bl2_list and element in tps_list and element not in ret_list:
            ret_list.append(element)
    return ret_list


def create_common_struct_def(tps_struct: StructDef, bl2_struct: StructDef) -> StructDef:
    assert tps_struct.full_name() == bl2_struct.full_name() and tps_struct.supers == bl2_struct.supers

    common_struct = bl2_struct
    common_struct.properties = get_common_elements(tps_struct.properties, bl2_struct.properties)
    return common_struct


def create_common_enum_def(tps_enum: EnumDef, bl2_enum: EnumDef) -> EnumDef:
    assert tps_enum.full_name() == bl2_enum.full_name()

    common_enum_def = EnumDef(names=tps_enum.names, package=tps_enum.package, type_cat=tps_enum.type_cat)
    for name, value in tps_enum.attributes.items():
        if bl2_enum.attributes.get(name) == value:
            common_enum_def.attributes[name] = value
    return common_enum_def


def create_common_class_def(tps_cls: ClassDef, bl2_cls: ClassDef) -> ClassDef | None:
    assert tps_cls.names == bl2_cls.names and tps_cls.package == bl2_cls.package and tps_cls.type_cat == bl2_cls.type_cat
    common_class_def = ClassDef(bl2_cls.names, bl2_cls.package, bl2_cls.type_cat, bl2_cls.supers, game=Game.COMMON)

    # Properties
    common_class_def.properties = get_common_elements(bl2_cls.properties, tps_cls.properties)

    # Functions
    common_class_def.functions = get_common_elements(bl2_cls.functions, tps_cls.functions)

    # Structs - Now we have to do a little prep since we want a base struct def that only includes common fields
    tps_structs: dict[str, StructDef] = {struct.name(): struct for struct in tps_cls.structs}
    bl2_structs: dict[str, StructDef] = {struct.name(): struct for struct in bl2_cls.structs}
    for struct_name in list(set(tps_structs.keys()) & set(bl2_structs.keys())):
        tps_struct = tps_structs.get(struct_name)
        bl2_struct = bl2_structs.get(struct_name)
        if tps_struct and bl2_struct and tps_struct.supers == bl2_struct.supers:
            common_class_def.structs.append(create_common_struct_def(tps_struct, bl2_struct))

    # Enums - Have to find common attributes
    tps_enums: dict[str, EnumDef] = {enum.name(): enum for enum in tps_cls.enums}
    bl2_enums: dict[str, EnumDef] = {enum.name(): enum for enum in bl2_cls.enums}
    for enum_name in list(set(tps_enums.keys()) & set(bl2_enums.keys())):
        tps_enum = tps_enums.get(enum_name)
        bl2_enum = bl2_enums.get(enum_name)
        if tps_enum and bl2_enum:
            common_class_def.enums.append(create_common_enum_def(tps_enum, bl2_enum))

    # Don't need common full names arg because when it doesn't find in list it'll revert to first arg anyway.
    common_class_def.set_game(Game.COMMON, [])
    return common_class_def


def get_game_elements(common_list: list, game_list: list) -> list:
    return [element for element in game_list if element not in common_list]


if __name__ == '__main__':
    with open(f'{CLASS_DEF_DATA_DIR}/TPS_class_defs.pkl', 'rb') as f:
        tps_class_defs: list[ClassDef] = pickle.load(f)

    with open(f'{CLASS_DEF_DATA_DIR}/BL2_class_defs.pkl', 'rb') as f:
        bl2_class_defs: list[ClassDef] = pickle.load(f)

    bl2_base: dict[str, ClassDef] = {cls.full_name(): cls for cls in bl2_class_defs}
    tps_base: dict[str, ClassDef] = {cls.full_name(): cls for cls in tps_class_defs}

    common: dict[str, ClassDef] = {}
    bl2: dict[str, ClassDef] = {}
    tps: dict[str, ClassDef] = {}

    # Get names list
    all_names = list(set(list(tps_base.keys()) + list(bl2_base.keys())))

    common_class_defs = []
    for cls_name in all_names:
        tps_cls = tps_base.get(cls_name)
        bl2_cls = bl2_base.get(cls_name)
        # There's one class with a different super, just going to keep that in game specific only
        if tps_cls and bl2_cls and (tps_cls.supers == bl2_cls.supers):
            common_class_def = create_common_class_def(tps_cls, bl2_cls)
            common_class_defs.append(common_class_def)

    common_names = list(set(name for ccd in common_class_defs for name in ccd.get_full_names()))

    for cls in common_class_defs:
        cls.set_game(Game.COMMON, common_names)

    # Doing this here since setting game for game specific changes some mutable refs in common that I don't want to deal with right now.
    with open(f'{CLASS_DEF_DATA_DIR}/common_class_defs_adj.pkl', 'wb') as f:
        pickle.dump(common_class_defs, f)

    for cls in tps_class_defs:
        cls.set_game(Game.TPS, common_names)

    with open(f'{CLASS_DEF_DATA_DIR}/tps_class_defs_adj.pkl', 'wb') as f:
        pickle.dump(tps_class_defs, f)

    for cls in bl2_class_defs:
        cls.set_game(Game.BL2, common_names)

    with open(f'{CLASS_DEF_DATA_DIR}/bl2_class_defs_adj.pkl', 'wb') as f:
        pickle.dump(bl2_class_defs, f)




