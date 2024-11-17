from pathlib import Path
import pandas
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from warnings import warn

from activityMatch import Activity, Player, CONSTRAINT_NAMES, BLACKLIST_KINDS
from timeslots import generate_timeslots_from_column_names

def load_activities(act_path: Path, verbose=True) -> List[Activity]:
    activities_df = pandas.read_csv(act_path, delimiter=',', quotechar='"', keep_default_na=False)
    activities: List[Activity] = []
    for (_, act) in activities_df.iterrows():
        if pandas.isna(act['name']):
            continue
        start = datetime.fromisoformat(act['start'])
        end = datetime.fromisoformat(act['end'])
        orga_names = act['orgas'].split(';')
        a = Activity(act['name'].strip(), int(act['capacity']), start, end, orga_names)
        activities.append(a)

    return activities

def load_players(players_path: Path, verbose=True) -> List[Player]:
    players_df = pandas.read_csv(players_path, delimiter=',', quotechar='"')
    players: List[Player] = []
    wishes_columns: List[str] = [c for c in players_df.columns
            if c.startswith("Vœu n°")]
    print(f"Detected {len(wishes_columns)} columns containing wishes")

    time_slots = generate_timeslots_from_column_names(players_df.columns)
    if verbose:
        print(f"Detected {len(time_slots)} columns containing a time slot.")

    for (_, p) in players_df.iterrows():
        if pandas.isna(p['name']):
            continue

        name = p['name'].strip()
        activity_names = [act_name.strip() for act_name in p[wishes_columns]
                          if not pandas.isna(act_name)]
        max_games = int(p['max_games']) if not pandas.isna(p['max_games']) else float("inf")
        ideal_games = int(p['ideal_games']) if not pandas.isna(p['ideal_games']) else max_games
        # Map each slot to a boolean: true if the player is available, false otherwise.
        availability = {slot:not pandas.isna(p[col]) for (col, slot) in time_slots.items()}
        constraints = set(cons for (col, cons) in CONSTRAINT_NAMES.items() if pandas.isna(p[col]))
        
        # Blacklists information:
        blacklist_names: Dict[int, List[str]] = {}
        for col_name, bl_kind in BLACKLIST_KINDS.items():
            names = str(p[col_name]).strip().split(';')
            names = [name for name in names if name != '' and name != 'nan']
            blacklist_names[bl_kind] = names

        player = Player(name, activity_names, availability,
                        max_games, ideal_games, constraints, blacklist_names)
        players.append(player)

    return players

def load_activities_and_players(act_path: Path, players_path: Path, verbose=True) -> Tuple[List[Activity], List[Player]]:
    """Loading the activities and the players.
    
    The activities data must be in a .csv file with the following columns:
    name : String with the name of the activity
    capacity : Max number of players that can join the activity
    start : When the activity starts, a datetime that can be parsed by pandas
    end : When the activity ends
    
    The players data must be a .csv file with the following columns :
    name : Name of the player
    wish <n> : Activity in rank <n> in their wishlist. These columns MUST be in the right order
    max_games : max number of activities to participate"""

    activities = load_activities(act_path, verbose)
    players = load_players(players_path, verbose)
    
    # Because activities and players have been loaded separately, then the organizers, 
    # activities and wishes are stored as strings. Now, we are going to replace them by
    # the corresponding `Player` and `Activity` objects.
    for act in activities:
        act.populate_organizers(players)
    for player in players:
        player.populate_wishes(activities)
        player.populate_blacklists(players)

    # Finally, we can remove wishes that players can't play, because either they are not
    # available, or because of a blacklist with the organizer.
    for player in players:
        if verbose:
            print(f"Processed player {player.name}")
        player.filter_availability(verbose=verbose)
 
    return (activities, players)
