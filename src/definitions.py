from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING
from copy import copy

from .game import Game
from .runner import register_module

if TYPE_CHECKING:
    from unrealsdk.unreal import UObject

DEFAULT_IMPORTS = [
    'from types import EllipsisType\n',
    'from typing import Annotated, Literal, Sequence\n',
    'from type_defs import OutParam, AttributeProperty\n',
    'from unrealsdk.unreal import BoundFunction, WrappedStruct, UObject, UClass\n',
    'from unrealsdk.unreal._uenum import UnrealEnum\n',
    '\n',
]

BUILTINS = [
    'int',
    'str',
    'bool',
    'float',
    'dict',
    'Callable',
    'type',
    'Final',
    'Any',
    'Optional',
    'list',
    'AttributeProperty',
    'Out'
]

DUPLICATE_STRUCTS = ['TerrainWeightedMaterial', 'ProjectileBehaviorSequenceStateData', 'CheckpointRecord']


class TypeCat(Enum):
    CLASS = auto()
    STRUCT = auto()
    ENUM = auto()
    FUNCTION = auto()
    CONST = auto()
    BUILTIN = auto()
    OTHER = auto()


@dataclass
class Context:
    game: Game
    cls: str


@dataclass
class BaseDef:
    names: list[str]  # From class on down. struct property would be [cls, struct, prop]
    package: str
    type_cat: TypeCat

    def outer_class_name(self) -> str:
        if self.type_cat == TypeCat.BUILTIN:
            return 'BUILTIN'
        return self.names[0]

    def name(self) -> str:
        """Name of the object without any outers."""
        return self.names[-1]

    def full_name(self) -> str:
        """Full name starting with package."""
        return f"{self.package}.{'.'.join(self.names)}"


    @classmethod
    def from_uobject[T: BaseDef](cls: type[T], obj: UObject) -> T:
        names = [obj.Name]
        outer = obj.Outer
        package = None
        while outer:
            if outer.Class.Name == 'Package':
                package = outer.Name
            else:
                names = [outer.Name] + names
            outer = outer.Outer
        if not package:
            raise ValueError(f"Couldn't find package for {obj._path_name()}")

        type_map = {
            'Class': TypeCat.CLASS,
            'ScriptStruct': TypeCat.STRUCT,
            'Enum': TypeCat.ENUM,
            'Function': TypeCat.FUNCTION,
        }

        type_cat = type_map.get(obj.Class.Name, TypeCat.OTHER)

        return cls(
            names=names,
            package=package,
            type_cat=type_cat,
        )


@dataclass
class TypeRef(BaseDef):
    '''
    Class for holding data for a type reference and generating string based on current context
    '''
    game: Game | None = None
    type_constructors: list[str] = field(default_factory=list)  # type[], Optional[], etc.

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TypeRef):
            return False
        if self.names == other.names and self.package == other.package and self.type_constructors == other.type_constructors \
                and self.type_cat == other.type_cat:
            return True
        return False

    def to_str(self, cls_name: str, cls_game: Game | None = None, super: bool=False) -> str:
        '''Tries for common prefix if available, reverts to game if not.
        No prefix if current class context is same as cls.'''
        if self.game is None:
            raise ValueError(f"game not set for object {self.name}")
        use_game = cls_game if cls_game else self.game


        ref = '.'.join([name for name in self.names])
        # Builtins don't get class/namespace prefix. CONST is str in Python
        if self.type_cat not in [TypeCat.BUILTIN, TypeCat.CONST] and use_game is not None:
            ref = f'{use_game.value}.{ref}'
        return ref


@dataclass
class PropertyRef:
    var_name: str
    type_ref: TypeRef

    def _type_additions(self, ref: str, setter: bool) -> str:
        if 'type' in self.type_ref.type_constructors:
            ref = f'type[{ref}]'
        
        # Enums can also accept ints. Users need to figure out which ints are valid.
        if self.type_ref.type_cat == TypeCat.ENUM:
            ref = f"{ref} | int"
        
        tuple_and_size = next((tcon for tcon in self.type_ref.type_constructors if 'tuple' in tcon), None)

        # Non arrays can all be None
        if 'list' not in self.type_ref.type_constructors and not tuple_and_size:
            if self.type_ref.type_cat in [TypeCat.CLASS, TypeCat.FUNCTION] and setter:
                ref = f'{ref} | None'

        elif tuple_and_size:
            size = tuple_and_size.split("_")[-1]
            if setter:
                ref = f'Annotated[Sequence[{ref}], "size: {size}"]'
            else:
                ref = f'tuple[{", ".join(ref for i in range(int(size)))}]'
            if len(ref) > 120: # Arbitrary line length
                ref = f'Annotated[{ref}, "size: {size}"]'
        elif 'list' in self.type_ref.type_constructors:
            ref = f'Sequence[{ref}]' if setter else f'list[{ref}]'
        if 'AttributeProperty' in self.type_ref.type_constructors:
            ref = f'Annotated[{ref}, AttributeProperty]'
        return ref

    def to_str(self, cls_name: str, tabs: int, cls_game: Game | None = None) -> str:
        # cls_game is current class context, used to determine what game return values and getters should use
        # Only needed here because same type_ref is used for both getters and setters'''
        getter_ref = self._type_additions(self.type_ref.to_str(cls_name, cls_game), False)
        setter_ref = self._type_additions(self.type_ref.to_str(cls_name), True)

        tab_str = tabs * '\t'
        lines = []
        lines.append(f'{tab_str}@property\n')
        lines.append(f'{tab_str}def {self.var_name}(self) -> {getter_ref}: ...\n')

        if self.type_ref.type_cat != TypeCat.CONST:
            lines.append(f'{tab_str}@{self.var_name}.setter\n')
            lines.append(f'{tab_str}def {self.var_name}(self, val: {setter_ref}) -> None: ...\n')
        return ''.join(lines)

    def make_struct_arg_str(self, cls_name: str, cls_game: Game):
        """Kind of hacky to put this here, but need a place to generate the args for make_struct helper. All args are optional"""
        type_str = self._type_additions(self.type_ref.to_str(cls_name, None), True)
        return f"{self.var_name}: {type_str} = ..."



@dataclass
class ParamRef:
    var_name: str
    type_ref: TypeRef

    def type_str(self, cls_name: str,  cls_game: Game | None = None) -> str:
        """There's a few instances of out params that are fixed arrays, so we have special logic to handle the double annotation here.
        This only returns the type, for params need to use to_str to include the var name"""
        annotations = []

        ref = self.type_ref.to_str(cls_name, cls_game)
        if 'type' in self.type_ref.type_constructors:
            ref = f'type[{ref}]'

        # Enums can also accept ints. Users need to figure out which ints are valid.
        if self.type_ref.type_cat == TypeCat.ENUM:
            ref = f"{ref} | int"

        # Fixed length array handling
        tuple_and_size = next((tcon for tcon in self.type_ref.type_constructors if 'tuple' in tcon), None)

        if 'list' not in self.type_ref.type_constructors and not tuple_and_size:
            if self.type_ref.type_cat in [TypeCat.CLASS, TypeCat.FUNCTION]:
                ref = f'{ref} | None'
        elif tuple_and_size:
            size = tuple_and_size.split("_")[-1]
            ref = f'Sequence[{ref}]'
            annotations.append(f'"size: {size}"')
        else:  # Params will accept any Sequence
            ref = f'Sequence[{ref}]'

        if 'Out' in self.type_ref.type_constructors:
            annotations.append("OutParam")

        if annotations:
            ref = f"Annotated[{ref}, {', '.join(annotations)}]"
        return ref

    def to_str(self, cls_name: str) -> str:
        """There's a few instances of out params that are fixed arrays, so we have special logic to handle the double annotation here."""
        ref = self.type_str(cls_name)

        if 'Optional' in self.type_ref.type_constructors:
            return f'{self.var_name}: {ref} = ...'
        return f'{self.var_name}: {ref}'


@dataclass
class ReturnRef:
    type_ref: TypeRef

    def to_str(self, cls_name: str, cls_game: Game | None = None, out_params: list[ParamRef] | None = None):

        ref = self.type_ref.to_str(cls_name)
        if 'type' in self.type_ref.type_constructors:
            ref = f'type[{ref}]'
        if 'list' in self.type_ref.type_constructors:
            ref = f'list[{ref}]'
        if 'Out' in self.type_ref.type_constructors:
            ref = f'Annotated[{ref}, OutParam]'

        if out_params:
            # Use type_str method from ParamRef to get the out param type without a var name.
            out_refs = ', '.join([op.type_str(cls_name, cls_game) for op in out_params])
            ref = 'EllipsisType' if ref == 'None' else ref
            return f'tuple[{ref}, {out_refs}]'
        else:
            return ref


@dataclass
class EnumDef(BaseDef):
    supers: list[TypeRef] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)

    def to_str(self, cls_game: Game) -> str:
        # if self.full_name() == "Core.Object.EDebugBreakType":
        #     print(self.supers)

        lines = []
        if self.supers:
            super_str = "(" + ", ".join([sup.to_str(self.name(), super=True) for sup in self.supers]) + ")"
        else:
            super_str = '(UnrealEnum)'
        lines.append(f'\tclass {self.name()}{super_str}:\n')
        # Docstring
        lines.append('\t\t"""\n')
        for attr, val in self.attributes.items():
            lines.append(f'\t\t{attr} = {val}\n')
        lines.append('\t\t"""\n')

        # Attributes
        for attr, val in self.attributes.items():
            lines.append(f'\t\t{attr}: int\n')
        if not self.attributes:
            lines.append('\t\tpass\n')
        lines.append('\n')
        
        # find_enum helper
        lines.append("\t\t@staticmethod\n")
        lines.append(f'\t\tdef find_enum(name: Literal["{self.name()}"]) -> {cls_game.value + "." + ".".join(self.names)}: ...')
        lines.append("\n\n")

        return "".join(lines)

@dataclass
class StructDef(BaseDef):
    supers: list[TypeRef] = field(default_factory=list)
    properties: list[PropertyRef] = field(default_factory=list)

    def to_str(self, cls_name: str, cls_game: Game) -> str:
        lines = []
        if self.supers:
            super_str = "(" + ', '.join([sup.to_str(self.name(), super=True) for sup in self.supers]) + ")"
        else:
            super_str = '(WrappedStruct)'
        prop_arg_refs = [prop.make_struct_arg_str(cls_name, cls_game) for prop in self.properties]
        lines.append(f'\tclass {self.name()}{super_str}:\n')
        # Docstring
        lines.append(f'\t\t"""\n\t\t{self.full_name()}\n\n')
        lines.extend([f'\t\t{prop_arg_ref}\n' for prop_arg_ref in prop_arg_refs])
        lines.append('\t\t"""\n')

        # Properties
        for prop in self.properties:
            lines.append(prop.to_str(cls_name, 2, cls_game))  # Two tabs because we're in a class in a struct

        # make_struct helper
        struct_name = self.full_name() if self.name() in DUPLICATE_STRUCTS else self.name()
        lines.append('\n\t\t@staticmethod\n')
        lines.append(
            f'\t\tdef make_struct(name: Literal["{struct_name}"], /{", *, " if prop_arg_refs else ""}{", ".join(prop_arg_refs)}) -> {cls_game.value + "." + ".".join(self.names)}: ...')

        lines.append('\n\n')
        return ''.join(lines)


@dataclass
class FunctionDef(BaseDef):
    params: list[ParamRef] = field(default_factory=list)
    ret: ReturnRef | None = None

    def _get_out_params(self) -> list[ParamRef]:
        res = []
        for param in self.params:
            if 'Out' in param.type_ref.type_constructors:
                res.append(param)
        return res

    def _return_str(self, cls_name: str, cls_game: Game | None = None) -> str:
        out_params = self._get_out_params()
        if not self.ret:
            return ''
        if out_params:
            return self.ret.to_str(cls_name, cls_game, out_params)
        else:
            return self.ret.to_str(cls_name)
        
    def _docstr_lines(self, cls_name: str) -> list[str]:
        docstr_lines = ['\t\t\t"""\n']
        if self.params:
            docstr_lines.append('\t\t\tArgs:\n')
        else:
            docstr_lines.append('\t\t\tNo args\n')
        for arg in self.params:
            docstr_lines.append(f'\t\t\t\t{arg.to_str(cls_name)}\n')
        docstr_lines.append('\n\t\t\tReturns:\n')
        docstr_lines.append(f'\t\t\t\t{self._return_str(cls_name)}\n')
        docstr_lines.append('\t\t\t"""\n\n')
        return docstr_lines
        

    # Defining function as a class so that we can get args and return values out for hook purposes
    def to_str(self, cls_name: str,  cls_game: Game | None = None) -> str:
        
        lines = []
        param_refs = ', '.join([param.to_str(cls_name) for param in self.params])

        # Metaclass
        lines.append(f'\tclass _{self.name()}(type):\n')
        lines.append(f'\t\tdef __call__(self{", " + param_refs if param_refs else ""}) -> {self._return_str(cls_name, cls_game)}:\n')
        lines.extend(self._docstr_lines(cls_name))

        # Main class
        lines.append(f'\tclass {self.name()}(BoundFunction, metaclass=_{self.name()}):\n')
        lines.append('\t\tdef __init__(self) -> None:\n')
        lines.extend(self._docstr_lines(cls_name=cls_name))
        lines.append(f'\t\tdef __call__(self{", " + param_refs if param_refs else ""}) -> {self._return_str(cls_name, cls_game)}:\n')
        lines.extend(self._docstr_lines(cls_name=cls_name))

        # args
        lines.append('\t\tclass args(WrappedStruct):\n')
        for param in self.params:
            lines.append(f'\t\t\t{param.to_str(cls_name)}\n')
        if not self.params:
            lines.append('\t\t\tpass\n')
        lines.append('\n')
        # ret
        lines.append(f'\t\ttype ret = {self._return_str(cls_name, cls_game)}\n\n')

       
        return ''.join(lines)


@dataclass
class ClassDef(BaseDef):
    supers: list[TypeRef] = field(default_factory=list)
    enums: list[EnumDef] = field(default_factory=list)
    structs: list[StructDef] = field(default_factory=list)
    properties: list[PropertyRef] = field(default_factory=list)
    functions: list[FunctionDef] = field(default_factory=list)
    game: Game | None = None

    def get_full_names(self) -> list[str]:
        names = [self.full_name()]
        names.extend(struct.full_name() for struct in self.structs)
        names.extend(enum.full_name() for enum in self.enums)
        names.extend(func.full_name() for func in self.functions)  # I guess we need these for DelegateProperties to reference.
        return names

    def set_game(self, try_game: Game, common_full_names: list[str]):
        self.game = try_game

        # Supers - add common version if available. Skip if already there or if we're setting to common.
        for sup in self.supers:
            if self.name() == sup.name():
                sup.game = Game.COMMON
            else:
                sup.game = try_game
        if try_game != Game.COMMON and self.name() not in [sup.name() for sup in self.supers] and self.full_name() in common_full_names:
            self.supers = [TypeRef(self.names, self.package, self.type_cat, Game.COMMON)] + self.supers

        # Enums
        for enum in self.enums:
            if try_game != Game.COMMON and enum.full_name() in common_full_names:
                enum.supers = [TypeRef(enum.names, enum.package, enum.type_cat, Game.COMMON)]
            
        # Structs
        for struct in self.structs:
            for sup in struct.supers:
                if struct.name() == sup.name():
                    sup.game = Game.COMMON
                else:
                    sup.game = try_game
            if try_game != Game.COMMON and struct.name() not in [sup.name() for sup in
                                                                 struct.supers] and struct.full_name() in common_full_names:
                struct.supers = [TypeRef(struct.names, struct.package, struct.type_cat, Game.COMMON)] + struct.supers
            for prop in struct.properties:
                if prop.type_ref.full_name() in common_full_names:
                    prop.type_ref.game = Game.COMMON
                else:
                    prop.type_ref.game = try_game

        # Properties
        for prop in self.properties:
            if prop.type_ref.full_name() in common_full_names:
                prop.type_ref.game = Game.COMMON
            else:
                prop.type_ref.game = try_game

        # Functions
        for func in self.functions:

            for param in func.params:
                if param.type_ref.full_name() in common_full_names:
                    param.type_ref.game = Game.COMMON
                else:
                    param.type_ref.game = try_game
            if func.ret:
                func.ret.type_ref.game = try_game
            # if func.name() == 'ClearResourcePoolReference' and try_game == Game.BL2:
            #     x=1

    def to_str(self) -> str:
        if self.game is None:
            raise ValueError(f"game not set for object {self.name}")

        lines = copy(DEFAULT_IMPORTS)

        lines.append('import common\n')
        if self.game != Game.COMMON and self.game is not None:
            lines.append(f'import {self.game.value}')
        lines.append('\n\n')

        # Class def and supers
        super_str = ', '.join([sup.to_str(self.name(), super=True) for sup in self.supers])
        if self.name() == 'Object' and self.game == Game.COMMON:
            super_str = 'UClass'
        lines.append(f'class {self.name()}{f"({super_str})" if super_str else ""}:\n')

        # Enums
        for enum in self.enums:
            lines.append(enum.to_str(self.game))

        # Structs
        deferred_struct_lines = []
        for struct in self.structs:
            for sup in struct.supers:
                if sup.name() == struct.name():
                    deferred_struct_lines.append(struct.to_str(self.name(), self.game))
                    break
            else:
                lines.append(struct.to_str(self.name(), self.game))
        lines.extend(deferred_struct_lines)

        # Properties
        deferred_properties_functions = []
        for prop in self.properties:
            if prop.var_name == self.name() or prop.var_name in BUILTINS:
                deferred_properties_functions.append(prop.to_str(self.name(), 1, self.game))
            else:
                lines.append(prop.to_str(self.name(), 1, self.game))
        lines.append('\n\n')

        # Functions
        for func in self.functions:
            if func.name() == self.name() or func.name() in BUILTINS:
                deferred_properties_functions.append(func.to_str(self.name(), self.game))
            else:
                lines.append(func.to_str(self.name(), self.game))
        lines.extend(deferred_properties_functions)

        if len(self.properties) + len(self.functions) + len(self.structs) + len(self.enums) == 0:
            lines.append('\tpass\n')

        # return lines
        return ''.join(lines)

register_module(__name__)
