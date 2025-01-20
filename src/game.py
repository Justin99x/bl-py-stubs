from enum import Enum

from .runner import register_module


class Game(Enum):
    BL2 = 'bl2'
    TPS = 'tps'
    COMMON = 'common'


# Only used for game_class_defs.py, set in that game's file only, don't copy this one over.
GAME = Game.BL2

register_module(__name__)