from enum import Enum


class Game(Enum):
    BL2 = 'bl2'
    TPS = 'tps'
    COMMON = 'common'


# Only used for game_class_defs.py, set in that game's file only, don't copy this one over.
GAME = Game.BL2