from baseball_types import Game
from typing import Dict, List, Tuple, Any
from event_log_parser import parse_events_directory
import itertools

import pybaseball
import pandas as pd
import numpy as np
import yaml
import os
from tqdm import tqdm


GAME_YAML_PATH = ".\\games.yaml"
DATASET_PATH = ".\\dataset.npz"
RETRO_EVENTS_DIR = "C:\\Users\\lplab\\Documents\\Retrosheet\\events"


def replacement_fip(year: int) -> float:
    average_fip_lut = {2003: 4.40, 2004: 4.46, 2005: 4.29, 2006: 4.53,
                       2007: 4.47, 2008: 4.32, 2009: 4.32, 2010: 4.08,
                       2011: 3.94, 2012: 4.01, 2013: 3.87, 2014: 3.74,
                       2015: 3.96, 2016: 4.19, 2017: 4.36, 2018: 4.15,
                       2019: 4.51, 2020: 4.45, 2021: 4.27, 2022: 3.97,
                       2023: 4.33}
    return average_fip_lut[year] + 0.2


def games_yaml(start_season, end_season) -> Dict[str, Any]:
    if os.path.exists(GAME_YAML_PATH):
        with open(GAME_YAML_PATH, "r") as file:
            data = yaml.safe_load(file)
            if data.get("start_season") == start_season and data.get("end_season") == end_season:
                # yaml has the right seasons, no need to do anything
                print("Successfully found cached game data")
                return data
        # have a file but it has the wrong contents -> delete
        print("Found cached data with incorrect contents. Deleting.")
        os.remove(GAME_YAML_PATH)
    # By the time we reach this point, there is no cached game yaml
    print("Parsing event files.")
    all_games = parse_events_directory(RETRO_EVENTS_DIR, start_season, end_season)
    contents = {"start_season": start_season,
                "end_season": end_season,
                "games": [game.__dict__ for game in all_games]}
    with open(GAME_YAML_PATH, "w") as file:
        yaml.safe_dump(contents, file)
    print("Game data cached successfully")
    return contents


def game_to_features(game: Game,
                     batting_data: pd.DataFrame,
                     pitching_data: pd.DataFrame,
                     batter_stats: List[Tuple[str, float]],
                     fielder_stats: List[Tuple[str, float]],
                     pitcher_stats: List[Tuple[str, float]]) -> np.ndarray:
    features = []
    for batter in itertools.chain(game.home_lineup, game.away_lineup):
        batter_data = batting_data[(batting_data["IDfg"]==batter) & (batting_data["Season"]==game.year)]
        for stat, default in batter_stats:
            val = default if len(batter_data)==0 else batter_data[stat].item()
            features.append(val)
    for fielder in itertools.chain(game.home_defense, game.away_defense):
        fielder_data = batting_data[(batting_data["IDfg"]==fielder) & (batting_data["Season"]==game.year)]
        for stat, default in fielder_stats:
            val = default if len(fielder_data)==0 else fielder_data[stat].item()
            features.append(val)
    for pitcher in [game.home_starter, game.away_starter]:
        pitcher_data = pitching_data[(pitching_data["IDfg"]==pitcher) & (pitching_data["Season"]==game.year)]
        for stat, default in pitcher_stats:
            val = default if len(pitcher_data)==0 else pitcher_data[stat].item()
            features.append(val)
    return np.array(features)


def game_from_dict(dct: Dict[str, Any]) -> Game:
    game = Game()
    for k, v in dct.items():
        if hasattr(game, k):
            game.__setattr__(k, v)
    return game


def generate_feature_names(batter_stats: List[str], fielder_stats: List[str], pitcher_stats: List[str]) -> List[str]:
    field_positions = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]
    feature_names = []
    for team, spot, stat in itertools.product(["home", "away"], range(9), batter_stats):
        feature_names.append(f"{team}_batter_{spot+1}_{stat}")
    for team, pos, stat in itertools.product(["home", "away"], field_positions, fielder_stats):
        feature_names.append(f"{team}_{pos}_{stat}")
    for team, stat in itertools.product(["home", "away"], pitcher_stats):
        feature_names.append(f"{team}_SP_{stat}")
    return feature_names


def generate_numpy_dataset(start_season, end_season):
    print("Fetching game log data")
    games_data = games_yaml(start_season, end_season)
    print("Fetching player batting and fielding stats")
    batting_data = pybaseball.batting_stats(start_season=start_season, end_season=end_season,
                                            stat_columns=["G", "BSR", "WRC_PLUS", "DEF", "WAR", "OPS"],
                                            split_seasons=True, qual=50)
    print("Fetching player pitching stats")
    pitching_data = pybaseball.pitching_stats(start_season=start_season, end_season=end_season,
                                              stat_columns=["G", "W", "FIP", "BABIP", "WAR"],
                                              split_seasons=True, qual=30)
    all_features = []
    all_results = []
    print("Parsing game features")
    for game_dict in tqdm(games_data["games"]):
        game = game_from_dict(game_dict)
        result = np.array([1 if game.home_win else 0])
        features = game_to_features(game, batting_data, pitching_data,
                                    batter_stats=[("BsR", -2.0),
                                                  ("wRC+", 80.0)],
                                    fielder_stats=[("Def", -4.0)],
                                    pitcher_stats=[("FIP", replacement_fip(game.year)),
                                                   ("BABIP", 0.305)])
        all_features.append(features)
        all_results.append(result)
    feature_names = generate_feature_names(["BsR", "wRC+"], ["Def"], ["FIP", "BABIP"])

    print("Creating and exporting numpy data")
    feature_names = np.array(feature_names, dtype=np.str_)
    features = np.stack(all_features, axis=0)
    results = np.stack(all_results, axis=0)
    np.savez(DATASET_PATH,
             feature_names=feature_names,
             features=features,
             results=results)
    print("Dataset generation complete")

if __name__ == "__main__":
    generate_numpy_dataset(2003, 2023)
