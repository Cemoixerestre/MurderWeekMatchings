from pathlib import Path
import pandas
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from warnings import warn
import re

from base import TimeSlot, Activity, Player, Constraints, BlacklistKind

YEAR = "2024"

def set_year(year):
    global YEAR
    YEAR = year

SLOT_TIMES = {
    'matin': ('08:00', '13:00'),
    'après-midi': ('13:00', '18:00'),
    'soir': ('18:00', '23:59')
}
NIGHT_SLOT_TIMES = ('00:00', '03:59')

def generate_timeslot_from_column_name(column_name: str) -> Optional[TimeSlot]:
    """
    If column_name corresponds to a slot, returns the corresponding TimeSlot
    object. Otherwise, returns None.

    Examples:
    - "Dimanche 25/08 après-midi" is mapped to the slot
      (YYYY-08-25 13:00, YYYY-08-25 18:00)
    - "Nuit de dimanche 25/08 à lundi 26/08" is mapped to the slot
      (YYYY-08-26 00:00, YYYY-08-26 03:59)
    - "Vœu n°3" is not a time slot. Returns None.
    """
    day_pattern = "(?P<day_name>\\S*) (?P<day>.{2})/(?P<month>.{2}) " \
                  "(?P<slot>\\S*)"
    night_pattern = "Nuit de \\S* .{2}/.{2} à " \
                    "(?P<day_name>\\S*) (?P<day>.{2})/(?P<month>.{2})"
    day_match = re.fullmatch(day_pattern, column_name)
    night_match = re.fullmatch(night_pattern, column_name)
    if day_match is not None:
        day_name = day_match.group("day_name")
        month = day_match.group("month")
        day_nb = day_match.group("day")
        slot_name = day_match.group("slot")
        start, end = SLOT_TIMES[slot_name]
    elif night_match is not None:
        day_name = night_match.group("day_name")
        month = night_match.group("month")
        day_nb = night_match.group("day")
        start, end = NIGHT_SLOT_TIMES
    else:
        return None

    start_date = datetime.fromisoformat(f"{YEAR}-{month}-{day_nb} {start}")
    end_date = datetime.fromisoformat(f"{YEAR}-{month}-{day_nb} {end}")
    slot = TimeSlot(start_date, end_date, column_name)
    assert slot.day_name.lower() == day_name.lower()
    return slot

def generate_timeslots_from_column_names(column_names: List[str]) -> Dict[str, TimeSlot]:
    """
    Take the list of all columns. To each of them that correspond to slot name in
    natural language, map them to a TimeSlot object.

    Examples:
    - "Dimanche 25/08 après-midi" is mapped to the slot
      (YYYY-08-25 13:00, YYYY-08-25 18:00)
    - "Nuit de dimanche 25/08 à lundi 26/08" is mapped to the slot
      (YYYY-08-26 00:00, YYYY-08-26 03:59)
    - "Vœu n°3" is not a time slot. It's therefore not a key in the result.
    """
    res = dict()
    for col in column_names:
        slot = generate_timeslot_from_column_name(col)
        if slot is not None:
            res[col] = slot

    return res

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

BLACKLIST_KINDS: Dict[str, BlacklistKind] = {
    "Ne pas jouer avec": BlacklistKind.DONT_PLAY_WITH,
    "Ne pas organiser pour": BlacklistKind.DONT_ORGANIZE_FOR,
    "Ne pas être organisée par": BlacklistKind.DONT_BE_ORGANIZED_BY
}

CONSTRAINT_NAMES: Dict[str, Constraints] = {
    "Jouer deux jeux dans la même journée": Constraints.TWO_SAME_DAY,
    "Jouer un soir et le lendemain matin": Constraints.NIGHT_THEN_MORNING,
    "Jouer deux jours consécutifs": Constraints.TWO_CONSECUTIVE_DAYS,
    "Jouer trois jours consécutifs": Constraints.THREE_CONSECUTIVE_DAYS,
    "Jouer plus de trois jours consécutifs": Constraints.MORE_CONSECUTIVE_DAYS,
    "Jouer et (co-)organiser dans la même journée":
        Constraints.PLAY_ORGA_SAME_DAY,
    "Jouer et (co-)organiser deux jours consécutifs":
        Constraints.PLAY_ORGA_TWO_CONSECUTIVE_DAYS
}

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

        # Constraints generation
        constraints = Constraints.NO_CONSTRAINT
        for col, constr in CONSTRAINT_NAMES.items():
            if pandas.isna(p[col]):
                constraints |= constr
        
        # Blacklists information:
        blacklist_names: Dict[BlacklistKind, List[str]] = {}
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
