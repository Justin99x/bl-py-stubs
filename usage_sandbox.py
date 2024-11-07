"""NOTES

- SDK returns tuples for out params
- How to make compatible with structs/enums libraries?
-


"""
from __future__ import annotations
from typing import Any, TYPE_CHECKING, Protocol, Type, overload

from unrealsdk.unreal import BoundFunction, UFunction, UObject, WrappedStruct

if TYPE_CHECKING:
    from common_structs import make_struct



lad = make_struct('InteractiveObjectBalanceDefinition.LootAttachmentData', True,)


#
#
# # if TYPE_CHECKING:
# #     from pystubs.bl2.obj import Object, _Args
#
# class classproperty(property):
#     def __get__(self, instance, owner):
#         return self.fget(owner)
#
#
# class PC:
#     # class _FMax(type):
#     #     def __call__(cls, a: float) -> float: ...
#
#     class _FMax(BoundFunction):
#         class _Args(WrappedStruct):
#             a: float
#             b: float
#
#         def _fmax(a: float, b: float) -> float: ...
#
#         args: _Args
#         object: "PC"
#         type ret = float
#         func: UFunction
#
#
#         def __call__(self, a: float, b: float) -> float: ...
#         # def __get__(self, instance, owner) -> _fmax: ...
#
#
#
#     FMax: _FMax
#
#
#     # def FMax(self, a: float, b: float) -> float: ...
#
#     # @property
#     # def FMax(self) -> _FMax: ...
#
#
# pc = PC()
#
# a = pc.FMax
# b = PC.FMax
#
#
# def fmax_callback(obj: PC, args: PC.FMax.args, ret: PC.FMax.ret, func: PC.FMax):
#
#     ...


# class PC:
#     class _FMax(BoundFunction):

#         class Args(WrappedStruct):
#             a: float
#             b: float

#         args= Type[Args]

#         type ret = float

#         def __call__(self, a: float, b: float) -> float: ...

#     FMax: _FMax

#     # def __init__(self):
#     #     self.FMax = self.FMax.__call__

# lines.append(f'\tclass _{self.name()}(type):\n')
# lines.append(f'\t\tdef __call__(self{", " + param_refs if param_refs else ""}) -> {self._return_str(cls_name)}: ...\n\n')



# class PC:
#     class _FMax(type):
#         """Docstring in metaclass"""
#         class args(WrappedStruct):
#             a: float
#             b: float
#
#         type ret = float
#
#         def __call__(self, a: float, b: float) -> float: ...
#
#
#
#     class FMax(metaclass=_FMax):
#         """Docstring in class"""
#
#         def __call__(self, a: float, b: float) -> float: ...
#
# class PCMeta(type):
#
#     class FMax:
#         class args(WrappedStruct):
#             b: float
#             a: float
#
#         ret = float
#
#         def __call__(self, a: float, b: float): ...
#
#     # @property
#     # def FMax(cls) -> _FMax: ...



class PC:

    class _FMax(Protocol):

        class args(WrappedStruct):
            b: float
            a: float

        ret = float

        def __call__(cls, a: float, b: float) -> float: ...

    FMax: _FMax



def fmax_callback(obj: PC, args: PC.FMax.args, ret: PC.FMax.ret, func: BoundFunction):

    pass

PC.FMax

pc = PC()
result = pc.FMax

'''
When base class def -> ability to access properties of FMax, but properties are themselves types
When instance -> ability to call FMax

'''


# Usage example


 # This behaves like calling the method and returns float
    #
    #
    # class _FMax:
    #     class args(WrappedStruct):
    #         b: float
    #         a: float
    #
    #     def __call__(self, a: float, b: float) -> float: ...
    #
    #
    # class _FMaxMeta(type):
    #     """Docstring in metaclass"""
    #
    #     @property
    #     def FMax(cls) -> PC._FMax: ...
    #
    # class FMax(metaclass=_FMaxMeta):
    #





#
'''
PC needs to have metaclass?
accessing attribute on PC gives 
'''



#
#
# class classproperty:
#     def __init__(self, func):
#         self.fget = func
#     def __get__(self, instance, owner):
#         return self.fget(owner)
#
#
# class PC:
#     class _FMaxProtocol(Protocol):
#         class args(WrappedStruct):
#             a: float
#             b: float
#
#         def __call__(self, a: float, b: float) -> float: ...
#
#     # def _FMax(self, a: float, b: float) -> float: ...
#
#     @property
#     def FMax(cls) -> _FMaxProtocol: ...




# Usage in a hook function
