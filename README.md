# bl-py-stubs

#### Checkout the [PythonSDK Mod DB](https://bl-sdk.github.io/) for instructions on how to develop with the legacy Python SDK

A repo for generating stub files for all unreal objects accessible through the Python SDK for Borderlands 2. You can use
these to get type checking, class/method signatures, and auto-complete features in your IDE when working with game
objects.

## Note on SDK versions

The files were created using the new unreal SDK nightly releases and were built by querying actual game objects, not
decompressed UPK files.
https://github.com/apple1417/willow-mod-manager/releases/tag/nightly

Due to minor differences in how SDK versions handle Unreal objects, two versions are provided to satisfy both legacy and
new SDK functionality. Main differences are:

- Return values for functions that have out params. New SDK always returns a Tuple with the function return value (
  Ellipsis if return value is null) and any out params. The legacy SDK only returns a Tuple of the out params if the
  function returns null.
- Stub structs, enums, and methods inherit from the relevant new SDK Python types (WrappedStruct, UnrealEnum, and
  BoundFunction). No such inheritance is supported in legacy.
- Structs define a stub for the `make_struct()` function in the new SDK.

## BL2/TPS Support

To make it possible to type hint when developing mods that work for BL2, TPS, or both, we set up a structure as follows:

- Three namespaces are available - common, bl2, and tps
- The common namespace contains all objects, properties, and methods that appear in both TPS and BL2. For methods, we
  also require the signatures to match.
- bl2 and tps namespaces define all objects for each. For objects that also exist in common, we inherit from the common
  definition, but redefine all members of the class so that we can adjust input and return types.
- When working with game specific objects (bl2/tps), all setters and method args are of the common type, when available.
  All return types and getters are of the game specific type. Thanks to apple1417 for this idea.
- Developers should import from the namespace that matches the game(s) they're developing for.

## Usage - New SDK

Download the gamestubs.zip file and extract it to desired location in your game folder. Can add bl2, common, and tps 
folders to .stubs folder that ships with the SDK to keep all stubs in one place.

<span style="color:red">Important:</span> You must change BoundFunction stub in the stubs that ship with the SDK to
inherit from typing.Protocol. Methods in these stubs inherit from BoundFunction, and it needs to be a Protocol to work
correctly in both regular code and in hooks.</span>.

#### Basic usage

```py
from __future__ import annotations  # Ensures type hints are ignored at runtime
from typing import TYPE_CHECKING, cast
from mods_base import get_pc

if TYPE_CHECKING:  # Only attempt import when type checking
    from common import WillowPlayerController  # from bl2 or from tps if making a mod for a specific game

# cast keeps type checker from complaining that get_pc returns a UObject.
# Alternatively, make your own get_pc that wraps the one from mods_base.
pc = cast("WillowPlayerController", get_pc())  
```

#### Hook usage

```py
from __future__ import annotations  # Ensures type hints are ignored at runtime
from typing import TYPE_CHECKING
from mods_base import hook
from unrealsdk.hooks import Type
from unrealsdk.unreal import BoundFunction

if TYPE_CHECKING:
    from bl2 import WillowPlayerController


@hook("WillowGame.WillowPlayerController:SaveGame", Type.PRE)
def save_game(obj: WillowPlayerController,
              args: WillowPlayerController.SaveGame.args,
              ret: WillowPlayerController.SaveGame.ret,
              func: BoundFunction):
    # args is a WrappedStruct
    # ret is whatever type the function returns
    pass
```

#### Struct usage

Might be more boilerplate than it's worth but I'm leaving it in. Simple usage is just
`location: Object.Vector = make_struct(*args, **kwargs)`, and hover over `Object.Vector` to see the dosctring with arg
info.

```py
from __future__ import annotations
from typing import TYPE_CHECKING
from unrealsdk import make_struct

if TYPE_CHECKING:
    from bl2 import Object

    # For type checking we use our custom stubs with matching signature
    make_struct_vector = Object.Vector.make_struct
    make_struct_rotator = Object.Rotator.make_struct
else:
    # Runtime we're still using the unrealsdk make_struct
    make_struct_vector = make_struct_rotator = make_struct

# These are now type hinted
location = make_struct_vector('Vector', True, X=0, Y=0, Z=0)
rotation = make_struct_rotator('Rotator', True, Pitch=0, Yaw=0, Roll=0)
```

#### Enum usage

```py
from __future__ import annotations  # Ensures type hints are ignored at runtime
from typing import TYPE_CHECKING, cast
from mods_base import get_pc
from unrealsdk import find_enum

if TYPE_CHECKING:
    from bl2 import WillowPlayerController

e_isa: WillowPlayerController.EInstinctSkillActions = find_enum('EInstinctSkillActions')

pc = cast("WillowPlayerController", get_pc())
pc.NotifyInstinctSkillAction(e_isa.ISA_KilledEnemy)  # Possible enum values are type hinted.
```

## Usage - Legacy SDK

Download the legacy_gamestubs.zip file and extract it to desired location in your game folder. Recommend
pystubs folder go in the Win32 folder and set it as a source root/directory in your IDE.

#### Basic usage

```py
from __future__ import annotations  # Ensures type hints are ignored at runtime
from typing import TYPE_CHECKING
import unrealsdk

if TYPE_CHECKING:  # Only attempt import when type checking
    from common import WillowPlayerController  # from bl2 or from tps if making a mod for a specific game


# Example usage for WillowPlayerController    
def get_wpc() -> WillowPlayerController:
    return unrealsdk.GetEngine().GamePlayers[0].Actor


PC = get_wpc()  # Auto-complete now available for PC
```

#### Hook usage

```py
from __future__ import annotations  # Ensures type hints are ignored at runtime
from typing import TYPE_CHECKING
from unrealsdk import UFunction

if TYPE_CHECKING:
    from bl2 import WillowPlayerController


@Hook("WillowGame.WillowPlayerController.SaveGame")
def save_game(caller: WillowPlayerController, function: UFunction, params: WillowPlayerController.SaveGame.args):
    # Type hinting available for caller and params
    return True
```

#### Struct usage (using Structs library)

```py
from __future__ import annotations  # Ensures type hints are ignored at runtime
from typing import TYPE_CHECKING
from Mods.Structs import Vector

if TYPE_CHECKING:
    from tps import Object

location: Object.Vector = Vector(0, 0, 0)
```

## Additional Information

- Namespaces are consistent with UnrealScript namespaces.
    - `from Engine import Actor` -> Resolves to the Actor class
    - `from Engine.Actor import EMoveDir` -> Resolves to EMoveDir enum defined in Actor class
- All inheritances are preserved.
  `WillowPlayerController -> GearboxPlayerController -> GamePlayerController -> PlayerController -> Controller -> Actor -> Object -> UObject`
- Unreal flags and types are converted to Python types
    - enum -> UnrealEnum
    - struct -> class
    - optional -> default argument
    - bool -> bool
    - byte -> int
    - const -> str
    - float -> float
    - name -> str
    - str -> str
    - map -> dict
    - array -> list
    - delegate -> Callable[]
    - state -> Ignored these for now as they provide overrides to other methods
- Additionally, two custom types are defined for information purposes
    - Out[] is used to denote that a parameter is an out parameter
    - AttributeProperty[] is used to identify attribute properties
        - FloatAttributeProperty -> AttributeProperty[float]
        - IntAttributeProperty -> AttributeProperty[int]
        - ByteAttributeProperty -> AttributeProperty[int]



