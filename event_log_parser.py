from baseball_types import Game
from typing import List, Dict, Iterable

from copy import deepcopy
from pathlib import Path
from tqdm import tqdm
from pybaseball import playerid_reverse_lookup


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

            elif line.startswith("info,wp"):
                winning_pitcher = line[8:].strip()

            elif line.startswith("start"):
                # Parse out relevant info
                player_info = line.split(",")
                retro_id = player_info[1]
                home = player_info[3]=="1"
                lineup_position = int(player_info[4])
                field_position = int(player_info[5])

                # Check if this player is the winning pitcher
                if retro_id == winning_pitcher:
                    current_game.home_win = home

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
                    current_game.home_win = player_info[3]=="1"

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
    for year in range(start_season, end_season+1):
        n_files = count_files(dir.glob(f"{year}*"))
        for file in tqdm(dir.glob(f"{year}*"), desc=str(year), total=n_files, unit="file", ncols=80):
            games = parse_event_file(file, cached_ids=player_ids)
            all_games.extend(games)
    return all_games


if __name__ == "__main__":
    # PATH = "C:\\Users\\lplab\\Documents\\Retrosheet\\events\\2003BAL.EVA"
    # game_list = parse_event_file(PATH)
    # print(game_list[0].home_lineup, game_list[0].home_win)
    PATH = "C:\\Users\\lplab\\Documents\\Retrosheet\\events"
    parse_events_directory(PATH, 2003, 2023)
