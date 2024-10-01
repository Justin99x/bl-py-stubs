# bl-py-stubs

#### Checkout the [PythonSDK Mod DB](https://bl-sdk.github.io/) for instructions on how to develop with the Python SDK

Stub files for all unreal objects accessible through the Python SDK for Borderlands 2. You can use these to get type checking,
class/method signatures, and auto-complete features in your IDE when working with game objects.

## Note on SDK versions

The files were created using the new unreal SDK nightly releases and were built by querying actual game objects, not
decompressed UPK files.
https://github.com/apple1417/willow-mod-manager/releases/tag/nightly

The resulting files are purely based on the game's unreal objects and do not use the SDK as a dependency, and are
therefore useful for devs using either the old or new SDK.

## Usage - Legacy SDK

- Download the pystubs.zip file and extract it to desired location in your game folder. If using legacy SDK, recommend
  pystubs folder go in the Win32 folder and set it as a source root/directory in your IDE.
- Example usage

```py
from __future__ import annotations                  # Ensures type hints are ignored at runtime

from typing import TYPE_CHECKING

import unrealsdk

if TYPE_CHECKING:                                   # Only attempt import when type checking
    from WillowGame import WillowPlayerController   # Requires your IDE to recognize pystubs as a source root/directory

# Example usage for WillowPlayerController    
def get_wpc() -> WillowPlayerController:
    return unrealsdk.GetEngine().GamePlayers[0].Actor

PC = get_wpc()                                      # Auto-complete now available for PC
```

## Usage - New SDK

TBD

## Additional Information

- Namespaces are consistent with UnrealScript namespaces.
    - `from Engine import Actor` -> Resolves to the Actor class
    - `from Engine.Actor import EMoveDir` -> Resolves to EMoveDir enum defined in Actor class
- All inheritances and associated attributes and methods are preserved.
    - `WillowPlayerController -> GearboxPlayerController -> GamePlayerController -> PlayerController -> Controller -> Actor -> Object`
- Unreal flags and types are converted to Python types
    - enum -> IntFlag
    - struct -> class
    - optional -> Optional[]
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
