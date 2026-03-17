"""Enums for March Madness Bracket Predictor.

Defines Region and RoundName enumerations used throughout the bracket prediction system.
"""

from enum import Enum


class Region(str, Enum):
    """Tournament region enumeration.
    
    Represents the four geographic regions in the NCAA March Madness tournament.
    """
    EAST = "East"
    WEST = "West"
    SOUTH = "South"
    MIDWEST = "Midwest"


class RoundName(str, Enum):
    """Tournament round enumeration.
    
    Represents the six rounds of the NCAA March Madness tournament,
    from the Round of 64 through the Championship.
    """
    ROUND_OF_64 = "Round of 64"
    ROUND_OF_32 = "Round of 32"
    SWEET_16 = "Sweet 16"
    ELITE_8 = "Elite 8"
    FINAL_FOUR = "Final Four"
    CHAMPIONSHIP = "Championship"
