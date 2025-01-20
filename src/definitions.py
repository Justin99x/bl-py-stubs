from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, TYPE_CHECKING
from copy import copy

from .game import Game
from .runner import register_module

if TYPE_CHECKING:
    from unrealsdk.unreal import UObject

DEFAULT_IMPORTS = [
    'from typing import Type, List, Tuple, Annotated, Literal, Sequence\n'
    'from type_defs import OutParam, AttributeProperty\n',
    'from unrealsdk.unreal import BoundFunction, WrappedStruct, UObject, UClass\n'
    'from unrealsdk.unreal._uenum import UnrealEnum\n',
    '\n'
]

LEGACY_DEFAULT_IMPORTS = [
    'from typing import Type, List, Tuple, Annotated, Protocol, Literal\n'
    'from type_defs import OutParam, AttributeProperty\n',
    '\n'
]

BUILTINS = [
    'int',
    'str',
    'bool',
    'float',
    'dict',
    'Callable',
    'Type',
    'Final',
    'Any',
    'Optional',
    'List',
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
    names: List[str]  # From class on down. struct property would be [cls, struct, prop]
    package: str
    type_cat: TypeCat

    def outer_class_name(self) -> str:
        if self.type_cat == TypeCat.BUILTIN:
            return 'BUILTIN'
        return self.names[0]

    def name(self) -> str:
        return self.names[-1]

    def full_name(self) -> str:
        return f"{self.package}.{'.'.join(self.names)}"

    @classmethod
    def from_uobject(cls, obj: UObject) -> "BaseDef":
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
    game: Optional[Game] = None
    type_constructors: List[str] = field(default_factory=list)  # Type[], Optional[], etc.

    def __eq__(self, other: TypeRef) -> bool:
        if self.names == other.names and self.package == other.package and self.type_constructors == other.type_constructors \
                and self.type_cat == other.type_cat:
            return True
        return False

    def to_str(self, cls_name: str, override_game: Optional[Game] = None) -> str:
        '''Tries for common prefix if available, reverts to game if not.
        No prefix if current class context is same as cls.'''
        use_game = override_game if override_game else self.game
        if cls_name in self.names:
            # Referencing a child of same class
            return self.names[-1]

        ref = '.'.join([name for name in self.names])
        # Builtins don't get class/namespace prefix. CONST is str in Python
        if self.type_cat not in [TypeCat.BUILTIN, TypeCat.CONST]:
            ref = f'{use_game.value}.{ref}'
        return ref


@dataclass
class PropertyRef:
    var_name: str
    type_ref: TypeRef

    def _type_additions(self, ref: str, setter: bool):
        if self.type_ref.names[0] == 'WillowEquipAbleItem':
            x=1
        if 'Type' in self.type_ref.type_constructors:
            ref = f'Type[{ref}]'
        tuple_and_size = next((tcon for tcon in self.type_ref.type_constructors if 'Tuple' in tcon), None)
        # Non arrays can all be None
        if not 'List' in self.type_ref.type_constructors and not tuple_and_size:
            if self.type_ref.type_cat in [TypeCat.CLASS, TypeCat.FUNCTION] and setter:
                ref = f'{ref} | None'
        elif tuple_and_size:
            size = tuple_and_size.split("_")[-1]
            if setter:
                ref = f'Annotated[Sequence[{ref}], "size: {size}"]'
            else:
                ref = f'Tuple[{", ".join(ref for i in range(int(size)))}]'
            if len(ref) > 120: # Arbitrary line length
                ref = f'Annotated[{ref}, "size: {size}"]'
        elif 'List' in self.type_ref.type_constructors:
            ref = f'Sequence[{ref}]' if setter else f'List[{ref}]'
        if 'AttributeProperty' in self.type_ref.type_constructors:
            ref = f'Annotated[{ref}, AttributeProperty]'
        return ref

    def to_str(self, cls_name: str, tabs: int, cls_game: Optional[Game] = None) -> str:
        '''cls_game is current class context, used to determine what game return values and getters should use
        Only needed here because same type_ref is used for both getters and setters'''
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
        return self._type_additions(self.type_ref.to_str(cls_name, None), True)


@dataclass
class ParamRef:
    var_name: str
    type_ref: TypeRef

    def type_str(self, cls_name: str) -> str:
        """There's a few instances of out params that are fixed arrays, so we have special logic to handle the double annotation here.
        This only returns the type, for params need to use to_str to include the var name"""
        annotations = []

        ref = self.type_ref.to_str(cls_name)
        if 'Type' in self.type_ref.type_constructors:
            ref = f'Type[{ref}]'

        tuple_and_size = next((tcon for tcon in self.type_ref.type_constructors if 'Tuple' in tcon), None)

        if not 'List' in self.type_ref.type_constructors and not tuple_and_size:
            if self.type_ref.type_cat in [TypeCat.CLASS, TypeCat.FUNCTION]:
                ref = f'{ref} | None'
        elif tuple_and_size:
            size = tuple_and_size.split("_")[-1]
            ref = f'Sequence[{ref}]'
            annotations.append(f'"size: {size}"')
        else:  # Params will accept any Sequence
            ref = f'Sequence[{ref}]'

        if 'Out' in self.type_ref.type_constructors:
            annotations.append(f"OutParam")
            # ref = f'Annotated[{ref}, OutParam]'

        if annotations:
            ref = f"Annotated[{ref}, {', '.join(annotations)}]"
        return ref

    def to_str(self, cls_name: str) -> str:
        """There's a few instances of out params that are fixed arrays, so we have special logic to handle the double annotation here."""
        ref = self.type_str(cls_name)

        if 'Optional' in self.type_ref.type_constructors:
            return f'{self.var_name}: {ref} = ...'
        else:
            return f'{self.var_name}: {ref}'


@dataclass
class ReturnRef:
    type_ref: TypeRef

    # def _out_param_to_str(self, cls_name: str, out_param: ParamRef):
    #
    #     ref = out_param.type_ref.to_str(cls_name, self.type_ref.game)
    #     tuple_and_size = next((tcon for tcon in out_param.type_ref.type_constructors if 'Tuple' in tcon), None)
    #     if 'Type' in out_param.type_ref.type_constructors:
    #         ref = f'Type[{ref}]'
    #     if not 'List' in out_param.type_ref.type_constructors and not tuple_and_size:
    #         if self.type_ref.type_cat in [TypeCat.CLASS, TypeCat.FUNCTION]:
    #             ref = f'{ref} | None'
    #     elif tuple_and_size:
    #         size = tuple_and_size.split("_")[-1]
    #         ref = f'Sequence[{ref}]'
    #         annotations.append(f'"size: {size}"')
    #     else:  # Params will accept any Sequence
    #         ref = f'Sequence[{ref}]'
    #     if 'List' in out_param.type_ref.type_constructors:
    #         ref = f'List[{ref}]'
    #
    #     if 'Out' in out_param.type_ref.type_constructors:
    #         ref = f'Annotated[{ref}, OutParam]'
    #     else:
    #         raise ValueError("Shouldn't call out_param_to_str on a non out param")
    #
    #     return ref

    def to_str(self, cls_name: str, out_params: Optional[List[ParamRef]] = None, legacy: bool = False):
        '''No override needed here because we set it in set_game()'''

        ref = self.type_ref.to_str(cls_name)
        if 'Type' in self.type_ref.type_constructors:
            ref = f'Type[{ref}]'
        if 'List' in self.type_ref.type_constructors:
            ref = f'List[{ref}]'
        if 'Out' in self.type_ref.type_constructors:
            ref = f'Annotated[{ref}, OutParam]'

        if out_params:
            # Use type_str method from ParamRef to get the out param type without a var name.
            out_refs = ', '.join([op.type_str(cls_name) for op in out_params])
            if legacy and ref == 'None':
                return f'Tuple[{out_refs}]' if len(out_params) > 1 else out_refs
            else:
                ref = 'Ellipsis' if ref == 'None' else ref
                return f'Tuple[{ref}, {out_refs}]'
        else:
            return ref


@dataclass
class EnumDef(BaseDef):
    attributes: dict = field(default_factory=dict)

    def to_str(self, legacy: bool = False) -> str:
        lines = []
        super_str = '(IntFlag)' if legacy else '(UnrealEnum)'
        lines.append(f'\tclass {self.name()}{super_str}:\n')
        # Docstring
        lines.append('\t\t"""\n')
        for attr, val in self.attributes.items():
            lines.append(f'\t\t{attr} = {val}\n')
        lines.append('\t\t"""\n')

        # Attributes
        for attr, val in self.attributes.items():
            lines.append(f'\t\t{attr} = {val}\n')
        if not self.attributes:
            lines.append(f'\t\tpass\n')
        lines.append('\n\n')
        return ''.join(lines)


@dataclass
class StructDef(BaseDef):
    supers: List[TypeRef] = field(default_factory=list)
    properties: List[PropertyRef] = field(default_factory=list)

    def to_str(self, cls_name: str, cls_game: Game, legacy: bool = False) -> str:
        lines = []
        super_str = '(WrappedStruct)' if not legacy else ''
        prop_arg_refs = [f'{prop.var_name}: {prop.make_struct_arg_str(cls_name, cls_game)}' for prop in self.properties]
        lines.append(f'\tclass {self.name()}{super_str}:\n')
        # Docstring
        lines.append(f'\t\t"""\n\t\t{self.full_name()}\n\n')
        lines.extend([f'\t\t{prop_arg_ref}\n' for prop_arg_ref in prop_arg_refs])
        lines.append('\t\t"""\n')

        for prop in self.properties:
            lines.append(prop.to_str(cls_name, 2, cls_game))  # Two tabs because we're in a class in a struct

        if not legacy:
            struct_name = self.full_name() if self.name() in DUPLICATE_STRUCTS else self.name()
            lines.append('\n\t\t@staticmethod\n')
            lines.append(
                f'\t\tdef make_struct(name: Literal["{struct_name}"], fully_qualified: Literal[True], /{", *, " if prop_arg_refs else ""}{", ".join(prop_arg_refs)}) -> {cls_game.value + "." + ".".join(self.names)}: ...')
        elif len(self.properties) == 0:
            lines.append('\t\tpass')

        lines.append('\n\n')
        return ''.join(lines)


@dataclass
class FunctionDef(BaseDef):
    params: List[ParamRef] = field(default_factory=list)
    ret: Optional[ReturnRef] = None

    def _get_out_params(self) -> List[ParamRef]:
        res = []
        for param in self.params:
            if 'Out' in param.type_ref.type_constructors:
                res.append(param)
        return res

    def _return_str(self, cls_name: str, legacy: bool = False):
        out_params = self._get_out_params()
        if out_params:
            return self.ret.to_str(cls_name, out_params, legacy=legacy)
        else:
            return self.ret.to_str(cls_name, legacy=legacy)

    # Defining function as a class so that we can get args and return values out for hook purposes
    def to_str(self, cls_name: str, legacy: bool = False) -> str:
        bound_function_str = '(BoundFunction)' if not legacy else ''
        wrapped_struct_str = '(WrappedStruct)' if not legacy else ''
        lines = []
        param_refs = ', '.join([param.to_str(cls_name) for param in self.params])
        # Protocol
        lines.append(f'\tclass _{self.name()}{bound_function_str}:\n')
        # args
        lines.append(f'\t\tclass args{wrapped_struct_str}:\n')
        for param in self.params:
            lines.append(f'\t\t\t{param.to_str(cls_name)}\n')
        if not self.params:
            lines.append('\t\t\tpass\n\n')
        # ret
        lines.append(f'\t\ttype ret = {self._return_str(cls_name, legacy=legacy)}\n\n')
        # Make it callable
        lines.append(
            f'\t\tdef __call__(self{", " + param_refs if param_refs else ""}) -> {self._return_str(cls_name, legacy=legacy)}: ...\n\n')

        # Class attribute and docstring
        lines.append(f'\t{self.name()}: _{self.name()}\n')
        lines.append('\t"""\n')
        for arg in self.params:
            lines.append(f'\t{arg.to_str(cls_name)}\n')
        if not self.params:
            lines.append(f'\tNo args\n')
        lines.append('\n')
        lines.append(f'\tReturns: {self._return_str(cls_name, legacy=legacy)}\n\t"""\n\n')

        return ''.join(lines)


@dataclass
class ClassDef(BaseDef):
    supers: List[TypeRef] = field(default_factory=list)
    enums: List[EnumDef] = field(default_factory=list)
    structs: List[StructDef] = field(default_factory=list)
    properties: List[PropertyRef] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    game: Optional[Game] = None

    def get_full_names(self) -> List[str]:
        names = [self.full_name()]
        names.extend(struct.full_name() for struct in self.structs)
        names.extend(enum.full_name() for enum in self.enums)
        names.extend(func.full_name() for func in self.functions)  # I guess we need these for DelegateProperties to reference.
        return names

    def set_game(self, try_game: Game, common_full_names: List[str]):
        self.game = try_game

        # Supers - add common version if available. Skip if already there or if we're setting to common.
        for sup in self.supers:
            if self.name() == sup.name():
                sup.game = Game.COMMON
            else:
                sup.game = try_game
        if try_game != Game.COMMON and self.name() not in [sup.name() for sup in self.supers] and self.full_name() in common_full_names:
            self.supers = [TypeRef(self.names, self.package, self.type_cat, Game.COMMON)] + self.supers

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

    def to_str(self, legacy: bool = False) -> str:
        lines = copy(DEFAULT_IMPORTS)
        if legacy:
            lines = copy(LEGACY_DEFAULT_IMPORTS)

        lines.append('import common\n')
        if self.game != Game.COMMON:
            lines.append(f'import {self.game.value}')
        lines.append('\n\n')

        # Class def and supers
        super_str = ', '.join([sup.to_str(self.name()) for sup in self.supers])
        if self.name() == 'Object':
            super_str = 'UClass'
        lines.append(f'class {self.name()}{f"({super_str})" if super_str else ""}:\n')

        # Enums
        for enum in self.enums:
            lines.append(enum.to_str(legacy=legacy))

        # Structs
        deferred_struct_lines = []
        for struct in self.structs:
            for sup in struct.supers:
                if sup.name() == struct.name():
                    deferred_struct_lines.append(struct.to_str(self.name(), self.game, legacy=legacy))
                    break
            else:
                lines.append(struct.to_str(self.name(), self.game, legacy=legacy))
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
                deferred_properties_functions.append(func.to_str(self.name(), legacy=legacy))
            else:
                lines.append(func.to_str(self.name(), legacy=legacy))
        lines.extend(deferred_properties_functions)

        if len(self.properties) + len(self.functions) + len(self.structs) + len(self.enums) == 0:
            lines.append(f'\tpass\n')

        # return lines
        return ''.join(lines)

register_module(__name__)
