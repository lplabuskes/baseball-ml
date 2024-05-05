from dataclasses import dataclass, field
from io import StringIO

@dataclass
class Game:
    year: int = 0
    month: int = 0
    day: int = 0
    game_number: int = 0  # 0=only, 1=first, 2=second

    home_team: str = ""  # Retrosheets team ID for the home team
    away_team: str = ""  # Retrosheets team ID for the away team

    home_wins: int = 0
    home_losses: int = 0
    away_wins: int = 0
    away_losses: int = 0

    home_lineup: list[int] = field(default_factory=lambda: [0]*9)  # A list of nine FanGraphs IDs in batting order
    away_lineup: list[int] = field(default_factory=lambda: [0]*9)  # A list of nine FanGraphs IDs in batting order

    home_defense: list[int] = field(default_factory=lambda: [0]*8)  # A list of eight FanGraphs IDs in positional order, excluding the pitcher
    away_defense: list[int] = field(default_factory=lambda: [0]*8)  # A list of eight FanGraphs IDs in positional order, excluding the pitcher

    home_starter: int = 0  # Home starter FanGraphs ID
    away_starter: int = 0  # Away starter FanGraphs ID

    home_team_won: bool = True


@dataclass
class OddsOutcome:
    home_line: int = 0
    away_line: int = 0
    home_implied_odds: float = 0.0
    away_implied_odds: float = 0.0
    home_team_won: bool = True


class NullIO(StringIO):
    def write(self, s: str) -> int:
        pass