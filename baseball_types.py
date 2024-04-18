from dataclasses import dataclass, field

@dataclass
class Game:
    year: int = 0

    home_lineup: list[int] = field(default_factory=lambda: [0]*9)  # A list of nine FanGraphs IDs in batting order
    away_lineup: list[int] = field(default_factory=lambda: [0]*9)  # A list of nine FanGraphs IDs in batting order

    home_defense: list[int] = field(default_factory=lambda: [0]*8)  # A list of eight FanGraphs IDs in positional order, excluding the pitcher
    away_defense: list[int] = field(default_factory=lambda: [0]*8)  # A list of eight FanGraphs IDs in positional order, excluding the pitcher

    home_starter: int = 0  # Home starter FanGraphs ID
    away_starter: int = 0  # Away starter FanGraphs ID

    home_win: bool = True