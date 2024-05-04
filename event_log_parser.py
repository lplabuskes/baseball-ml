from baseball_types import Game, NullIO
from typing import List, Dict, Tuple, Iterable

from copy import deepcopy
from pathlib import Path
import datetime
import sys
from tqdm import tqdm
import pandas as pd
from pybaseball import playerid_reverse_lookup, schedule_and_record, team_ids


def parse_event_file(path: str, cached_ids: Dict[str, int] = {}) -> List[Game]:
    games = []
    with open(path, 'r') as file:
        current_game: Game = None
        winning_pitcher = ""  # Keep track of these because for some reason the log doesn't say who won
        unknown_retro_ids = []

        for line in file:
            if line.startswith("id"):
                current_game = Game()

            elif line.startswith("info,date"):
                current_game.year = int(line[10:14])
                current_game.month = int(line[15:17])
                current_game.day = int(line[18:20])

            elif line.startswith("info,number"):
                current_game.game_number = int(line[-2])

            elif line.startswith("info,wp"):
                winning_pitcher = line[8:].strip()

            # Use the teams and date info later to determine team records
            # Not doing it as part of this function to cut down on web queries
            elif line.startswith("info,visteam"):
                current_game.away_team = line[13:].strip()

            elif line.startswith("info,hometeam"):
                current_game.home_team = line[14:].strip()

            elif line.startswith("start"):
                # Parse out relevant info
                player_info = line.split(",")
                retro_id = player_info[1]
                home = player_info[3]=="1"
                lineup_position = int(player_info[4])
                field_position = int(player_info[5])

                # Check if this player is the winning pitcher
                if retro_id == winning_pitcher:
                    current_game.home_team_won = home

                # Determine if we need to query pybaseball for FanGraphs ID
                if retro_id not in cached_ids:
                    unknown_retro_ids.append(retro_id)

                # Put player ID into required spots in lineup and defense
                if home:
                    if field_position == 1:
                        current_game.home_starter = retro_id
                    elif field_position > 1 and field_position < 10:
                        current_game.home_defense[field_position-2] = retro_id
                    if lineup_position > 0:
                        current_game.home_lineup[lineup_position-1] = retro_id
                else:
                    if field_position == 1:
                        current_game.away_starter = retro_id
                    elif field_position > 1 and field_position < 10:
                        current_game.away_defense[field_position-2] = retro_id
                    if lineup_position > 0:
                        current_game.away_lineup[lineup_position-1] = retro_id

            elif line.startswith("sub"):
                # We need this logic to figure out who the winning pitcher plays for
                player_info = line.split(",")
                if player_info[1] == winning_pitcher:
                    current_game.home_team_won = player_info[3]=="1"

            elif line.startswith("data") and current_game is not None:
                # This is our indicator for the end of the game
                # Don't count on hitting another ID because not applicable for last game in file
                
                # Query FanGraph ID's for our unknown players and add them to the cache
                player_id_table = playerid_reverse_lookup(unknown_retro_ids, key_type="retro")
                for retro_id in unknown_retro_ids:
                    fgid = player_id_table.loc[player_id_table["key_retro"]==retro_id]["key_fangraphs"].item()
                    cached_ids[retro_id] = fgid
                
                # Replace Retrosheet ID's with FanGraph ID's
                for idx, retro_id in enumerate(current_game.home_lineup):
                    current_game.home_lineup[idx] = cached_ids[retro_id]
                for idx, retro_id in enumerate(current_game.away_lineup):
                    current_game.away_lineup[idx] = cached_ids[retro_id]
                for idx, retro_id in enumerate(current_game.home_defense):
                    current_game.home_defense[idx] = cached_ids[retro_id]
                for idx, retro_id in enumerate(current_game.away_defense):
                    current_game.away_defense[idx] = cached_ids[retro_id]
                current_game.home_starter = cached_ids[current_game.home_starter]
                current_game.away_starter = cached_ids[current_game.away_starter]

                games.append(deepcopy(current_game))
                current_game = None
                winning_pitcher = ""
                unknown_retro_ids = []
    return games


def datestring(game: Game) -> str:
    date = datetime.datetime(game.year, game.month, game.day)
    out = date.strftime("%A, %b %d").replace(" 0", " ")
    if game.game_number != 0:
        out += f" ({game.game_number})"
    return out


def parse_record_table(df: pd.DataFrame) -> Tuple[int, int]:
    # df is a one row DataFrame wth columns: Date, W/L, W-L
    try:
        won_game = df["W/L"].item().startswith("W")
    except Exception as e:
        print(df)
        raise e
    wins, losses = [int(n) for n in df["W-L"].item().split("-")]
    if won_game:
        wins -= 1
    else:
        losses -= 1
    return wins, losses


def find_win_loss(games: List[Game], team_ids_cache: Dict[str, str]):
    cached_schedule_tables = {}
    team_id_lut = team_ids(season=games[0].year)
    silencer = NullIO()
    for game in tqdm(games, unit="game", ncols=80):
        for team in [game.home_team, game.away_team]:
            if team not in cached_schedule_tables:
                if game.year <= 2021:  # pybaseball team ID has data through 2021
                    br_team_id = team_id_lut[team_id_lut["teamIDretro"]==team]["teamIDBR"].item()
                    team_ids_cache[team] = br_team_id
                elif team in team_ids_cache:  # hope they didn't change between 2021 and 2023 :shrug:
                    br_team_id = team_ids_cache[team]
                else:
                    br_team_id = team

                sys.stdout = silencer
                tbl: pd.DataFrame = schedule_and_record(game.year, br_team_id)
                sys.stdout = sys.__stdout__

                tbl = tbl[["Date", "W/L", "W-L"]]
                cached_schedule_tables[team] = tbl

        date = datestring(game)
        home_table = cached_schedule_tables[game.home_team]
        home_table = home_table[home_table["Date"]==date]
        w, l = parse_record_table(home_table)
        game.home_wins = w
        game.home_losses = l

        away_table = cached_schedule_tables[game.away_team]
        away_table = away_table[away_table["Date"]==date]
        w, l = parse_record_table(away_table)
        game.away_wins = w
        game.away_losses = l


def count_files(iter: Iterable) -> int:
    # Vanity helper function for prettier progress bars
    n = 0
    for _ in iter:
        n += 1
    return n


def parse_events_directory(path: str, start_season: int, end_season: int) -> List[Game]:
    dir = Path(path)
    all_games = []
    player_ids = {}
    team_id_cache = {}
    for year in range(start_season, end_season+1):
        year_games = []
        n_files = count_files(dir.glob(f"{year}*"))
        for file in tqdm(dir.glob(f"{year}*"), desc=str(year), total=n_files, unit="file", ncols=80):
            games = parse_event_file(file, cached_ids=player_ids)
            year_games.extend(games)
        find_win_loss(year_games, team_id_cache)
        all_games.extend(year_games)
    return all_games


if __name__ == "__main__":
    # PATH = "C:\\Users\\lplab\\Documents\\Retrosheet\\events\\2003BAL.EVA"
    # game_list = parse_event_file(PATH)
    # print(game_list[0].home_lineup, game_list[0].home_win)
    PATH = "C:\\Users\\lplab\\Documents\\Retrosheet\\events"
    parse_events_directory(PATH, 2003, 2023)
