from pathlib import Path
import pandas
from typing import List, Optional, Dict, Tuple

from activityMatch import Activity, Player, Constraint
from timeSlots import generate_timeslots_from_column_names, WEEK_DAYS

def load_activities_and_players(act_path: Path, players_path: Path) -> Tuple[List[Activity], List[Player]]:
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

    # TODO: Manage players disponibility during the week to remove wishes for activities when the player is not there
    
    activities_df = pandas.read_csv(act_path, delimiter=',', quotechar='"', parse_dates=['start', 'end'])
    activities: List[Activity] = []
    orgas: List[str] = []
    for (_, act) in activities_df.iterrows():
        if pandas.isna(act['name']):
            continue
        a = Activity(act['name'].strip(), act['capacity'], act['start'], act['end'])
        activities.append(a)
        orgas.append(act['orgas'])

    players_df = pandas.read_csv(players_path, delimiter=',', quotechar='"')
    players: List[Player] = []
    wishes_columns: List[str] = [c for c in players_df.columns if c.startswith("wish")]
    print(f"Detected {len(wishes_columns)} columns containing wishes")

    day_columns: list[str] = [c for c in players_df.columns if
                              c.split(' ')[0] in WEEK_DAYS]

    time_slots = generate_timeslots_from_column_names(day_columns)

    blacklist: Dict[str, List[str]] = {}
    for (_, p) in players_df.iterrows():
        if pandas.isna(p['name']):
            continue

        name = p['name'].strip()
        # Convert the ranked names into a sorted list of Activities
        # Be careful, players rank a given activity but one activity may have multiple sessions.
        # So we get all the activities with this name and add them in order to the wishlist
        wishes = []
        for act_name in p[wishes_columns]:
            if pandas.isna(act_name):
                continue
            act = [act for act in activities if act.name == act_name.strip()]
            if act == []:
                print(f"WARNING. Could not find activity {act_name} in the activity list. "
                       "Check your activity file.")
            else:
                wishes.extend(act)

        max_games = int(p['max_games']) if not pandas.isna(p['max_games']) else None
        ideal_games = int(p['ideal_games']) if not pandas.isna(p['ideal_games']) else None
        blacklist[name] = str(p['blacklist']).strip().split(';')
        orga_player_same_day = not pandas.isna(p["Jouer et (co-)organiser dans la même journée"])

        # Load time availability and remove wishes when the player is not available
        non_availabilities = [slot for (col, slot) in time_slots.items() if pandas.isna(p[col])]

        # Generate constraints
        constraints = set(cons for (col, cons) in Constraint.NAMES.items() if pandas.isna(p[col]))

        players.append(Player(name, wishes, non_availabilities, max_activities=max_games, ideal_activities=ideal_games,
                              constraints=constraints, orga_player_same_day=orga_player_same_day))

    # Now that the players are created, populate the blacklists
    for (name, bl_names) in blacklist.items():
        player = [pl for pl in players if pl.name == name][0]
        bl = [find_player_by_name(b, players) for b in bl_names if b != '' and b != 'nan']

        for pl in bl:
            if pl is not None:
                player.add_blacklist_player(pl)
    
    # Populate the organizers
    for (act, orgas_list) in zip(activities, orgas):
        for name in orgas_list.split(';'):
            player = find_player_by_name(name.strip(), players)
            if player is not None:
                act.add_orga(player)
                player.add_orga(act)

    for player in players:
        print(f"Processed player {player.name}")
        player.filter_availability(verbose=True)
        player.update_wishlist(verbose=True)
        
    return (activities, players)


def find_player_by_name(name: str, players: List[Player]) -> Optional[Player]:
    p = [pl for pl in players if pl.name == name]
    if not p:
        print(f"Could not find player {name}")
        return None
    elif len(p) == 1:
        return p[0]
    else:
        raise ValueError(f"Several players corresponding to the name {name}")
