from __future__ import annotations  # Ensures type hints are ignored at runtime
from typing import TYPE_CHECKING, cast
from mods_base import get_pc
from unrealsdk import find_enum

if TYPE_CHECKING:
    from bl2 import WillowPlayerController

a: WillowPlayerController.EOnlineMessageType

e_isa: WillowPlayerController.EInstinctSkillActions = find_enum('EInstinctSkillActions')

pc = cast("WillowPlayerController", get_pc())
pc.NotifyInstinctSkillAction(e_isa.ISA_KilledEnemy)  # Possible enum values are type hinted.

