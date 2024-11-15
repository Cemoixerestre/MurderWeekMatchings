from pathlib import Path
import pandas
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from warnings import warn

from activityMatch import Activity, Player, CONSTRAINT_NAMES, BLACKLIST_KINDS
from timeslots import generate_timeslots_from_column_names

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

    activities_df = pandas.read_csv(act_path, delimiter=',', quotechar='"', keep_default_na=False)
    activities: List[Activity] = []
    orgas: List[str] = []
    for (_, act) in activities_df.iterrows():
        if pandas.isna(act['name']):
            continue
        start = datetime.fromisoformat(act['start'])
        end = datetime.fromisoformat(act['end'])
        a = Activity(act['name'].strip(), int(act['capacity']), start, end)
        activities.append(a)
        orgas.append(act['orgas'])

    players_df = pandas.read_csv(players_path, delimiter=',', quotechar='"')
    players: List[Player] = []
    wishes_columns: List[str] = [c for c in players_df.columns if c.startswith("Vœu n°")]
    print(f"Detected {len(wishes_columns)} columns containing wishes")

    time_slots = generate_timeslots_from_column_names(players_df.columns)
    if verbose:
        print(f"Detected {len(time_slots)} columns containing a time slot.")

    # TODO: replace these maps with attributes in the Player class.
    blacklist : Dict[Tuple[Player, int], List[str]] = {}
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

        # Generate constraints
        constraints = set(cons for (col, cons) in CONSTRAINT_NAMES.items() if pandas.isna(p[col]))

        player = Player(name, activity_names, availability,
                        max_activities=max_games, ideal_activities=ideal_games,
                        constraints=constraints)
        
        # Blacklists information:
        for col_name, bl_kind in BLACKLIST_KINDS.items():
            names = str(p[col_name]).strip().split(';')
            names = [name for name in names if name != '' and name != 'nan']
            blacklist[player, bl_kind] = names
        player.populate_wishes(activities)
        players.append(player)

    # Now that the players are created, populate the blacklists
    for (player, bl_kind), names in blacklist.items():
        for b in names:
            blacklisted = find_player_by_name(b, players)
            player.add_blacklist_players(blacklisted, bl_kind)
    
    # Populate the organizers
    for (act, orgas_list) in zip(activities, orgas):
        if orgas_list == "":
            # TODO: warn if no organizers are provided?
            continue
        for name in orgas_list.split(';'):
            player = find_player_by_name(name.strip(), players)
            if player is not None:
                act.add_orga(player)
                player.add_orga(act)

    for player in players:
        if verbose:
            print(f"Processed player {player.name}")
        player.filter_availability(verbose=verbose)
        # TODO: delete
        # player.update_wishlist(verbose=verbose)
        
    return (activities, players)


# TODO: doublon de Player.find_player_by_name(), retirer
def find_player_by_name(name: str, players: List[Player]) -> Optional[Player]:
    p = [pl for pl in players if pl.name == name]
    if not p:
        warn(f"Could not find player {name}")
        return None
    elif len(p) == 1:
        return p[0]
    else:
        raise ValueError(f"Several players corresponding to the name {name}")
