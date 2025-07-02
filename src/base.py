from __future__ import annotations

from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime, timedelta
from warnings import warn
from enum import Enum, Flag, auto

WEEK_DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

class TimeSlot:
    def __init__(self, start: datetime, end: datetime, name: Option[str]=None):
        """Create a timeslot.

        Arguments:
        - start: a datetime. The hour must be between 4AM and 8AM.
        - end: a datetime. The hour must be between 4AM and 8AM. It must be
          greater than start. It can be the same day as start, or the day after
          start.
        - Optional: a representation "name". It is used for columns extracted
          from the inscription file. The goal is to display
          "Lundi 24/08 matin" instead of "24/08 08:00-13:00". 
        """
        self.start = start
        self.end = end
        self.name: Option[str] = name
        assert self.start < self.end, \
            "Error: time slot should starts before it ends. " \
            f"day. Erroneous dates: start = {start} and end = {end}."
        assert self.end.day - self.start.day <= 1, \
            "Error: a game cannot be more than one day long. " \
            f"day. Erroneous dates: start = {start} and end = {end}."
        assert not (4 <= self.start.hour < 8), \
            f"Error: a game starts between 8:00 AM and 4:00 AM. " \
            f"Erroneous date: start = {start}"
        assert not (4 <= self.end.hour < 8), \
            f"Error: a game ends between 8:00 AM and 4:00 AM. " \
            f"Erroneous date: start = {start}"

        self.day_name: str = WEEK_DAYS[start.weekday()]

    def overlaps(self, other: TimeSlot) -> bool:
        if (self.start <= other.start) and (other.start < self.end):
            return True
        elif (other.start <= self.start) and (self.start < other.end):
            return True
        else:
            return False

    def __repr__(self):
        if self.name is not None:
            return self.name
        start_hour = f"{self.start.hour:02}:{self.start.minute:02}"
        end_hour = f"{self.end.hour:02}:{self.end.minute:02}"
        return f"{self.start.day:02}/{self.start.month:02} {start_hour}-{end_hour}"

    def __eq__(self, other):
        return (self.start, self.end) == (other.start, other.end)

    def __hash__(self):
        return hash((self.start, self.end))

    def disp_day(self) -> str:
        return f"{self.day_name} {self.start.day}"

    def disp_hour(self) -> str:
        return f"{self.start.hour:02}:{self.start.minute:02}-" \
               f"{self.end.hour:02}:{self.end.minute:02}"


class Activity:
    ACTIVE_ACTIVITIES = 0

    def __init__(
            self,
            name: str,
            capacity: int,
            start: datetime,
            end: datetime,
            orga_names: List[str]
        ):
        # Auto number the activities
        self.id = Activity.ACTIVE_ACTIVITIES
        Activity.ACTIVE_ACTIVITIES += 1

        self.name: str = name
        self.capacity: int = capacity
        self.timeslot = TimeSlot(start, end)
        self.orga_names = orga_names

        # Will be filled later, when the players are loaded.
        self.orgas: List[Player] = []

    def __repr__(self):
        return f"{self.id} | {self.name} | " \
               f"{self.timeslot}"

    def populate_organizers(self, players: List[Player]) -> None:
        for name in self.orga_names:
            player = find_player_by_name(name, players)
            if player is not None:
                self.orgas.append(player)
                player.organizing.append(self)

    def overlaps(self, slot: TimeSlot) -> bool:
        return self.timeslot.overlaps(slot)

    def date(self) -> datetime:
        # There is a possibility that the activity starts after midnight. In
        # this case, we take for the date the day before.
        # As no activity starts between 4AM and 8AM, we can just substract
        # 6 hours and obtain the start date.
        start_date = self.timeslot.start - timedelta(hours=6)
        return start_date.date()

    def night_then_morning(self, other: Activity) -> bool:
        if other.date() - self.date() != timedelta(days=1):
            return False
        return other.timeslot.start - self.timeslot.end <= timedelta(hours=12)


class Constraints(Flag):
    NO_CONSTRAINT = 0
    TWO_SAME_DAY = auto()
    NIGHT_THEN_MORNING = auto()
    TWO_CONSECUTIVE_DAYS = auto()
    THREE_CONSECUTIVE_DAYS = auto()
    MORE_CONSECUTIVE_DAYS = auto()
    PLAY_ORGA_SAME_DAY = auto()
    PLAY_ORGA_TWO_CONSECUTIVE_DAYS = auto()

class BlacklistKind(Enum):
    DONT_PLAY_WITH = auto()
    DONT_ORGANIZE_FOR = auto()
    DONT_BE_ORGANIZED_BY = auto()


class Player:
    ACTIVE_PLAYERS = 0

    def __init__(self, name: str,
                 initial_activity_names: List[Activity],
                 availabilities: Dict[TimeSlot, bool],
                 max_activities: Optional[int],
                 ideal_activities: Optional[int],
                 constraints: Constraints,
                 blacklist_names: Dict[BlacklistKind, List[str]]):
        # Auto number the players
        # Note: not used anymore, could be deleted.
        self.id = Player.ACTIVE_PLAYERS
        Player.ACTIVE_PLAYERS += 1

        self.name = name
        self.wishes: List[Activity] = []
        self.initial_activity_names = initial_activity_names
        self.ranked_activity_names: List[str] = []
        self.availability: Dict[TimeSlot, bool] = availabilities
        self.max_activities = max_activities
        self.ideal_activities = ideal_activities
        assert ideal_activities <= max_activities, \
               f"Player {name}: the number of ideal activities is larger " \
               f"than the maximal number of activities."
        self.constraints: Constraints = constraints
        self.blacklist_names: List[str] = blacklist_names

        # Blacklists sets are empty, and will be replaced later by players.
        self.blacklist: Dict[BlacklistKind, Set[Player]] = \
                        {bl_kind:set() for bl_kind in BlacklistKind}
        # Will be replaced later by activities.
        self.organizing: List[Activity] = []

    def populate_wishes(self, activities: List[Activity]) -> None:
        """
        Add a wish for any activity mentionned in the list of activity names.
        As an activity can be organized several times, several wishes of the
        same name may be added.
        """
        for act_name in self.initial_activity_names:
            act = [act for act in activities if act.name == act_name.strip()]
            if act == []:
                warn(f"Could not find activity {act_name} in the activity list. "
                      "Check your activity file.")
            else:
                self.wishes.extend(act)

    def populate_blacklists(self, players: List[Player]) -> None:
        for bl_kind, names in self.blacklist_names.items():
            for name in names:
                other = find_player_by_name(name, players)
                self.blacklist[bl_kind].add(other)

    def filter_availability(self, verbose:bool = False) -> None:
        """Function called at the beginning to filter impossible wishes.

        It filters out wishes where the player in unavailable, when it
        overlaps with the organization of a game, or wishes the same day
        as an orginazition (when the player asked not to participate
        and organize the same day).

        This procedure is called once after the initialization of players
        and activities.
        """
        if Constraints.PLAY_ORGA_SAME_DAY in self.constraints:
            activity_when_orga = [a for a in self.wishes for o in self.organizing
                                  if a.date() == o.date()]
            if verbose and activity_when_orga:
                print("Found wishes and activities the same day :")
                for a in set(activity_when_orga):
                    print(f"- {a}")

            for a in set(activity_when_orga):
                self.wishes.remove(a)

        if Constraints.PLAY_ORGA_TWO_CONSECUTIVE_DAYS in self.constraints:
            activity_orga_consecutive = {a for a in self.wishes
                                         for o in self.organizing
                                         if abs(a.date() - o.date()).days <= 1}
            if verbose and activity_orga_consecutive:
                print("Found wishes and activities on consecutive days :")
                for a in activity_orga_consecutive:
                    print(f"- {a}")

            for a in activity_orga_consecutive:
                self.wishes.remove(a)

        organizing = [a for a in self.wishes for o in self.organizing
                       if a.overlaps(o.timeslot)]
        if verbose and organizing:
            print("Found wishes when organizing :")
            for a in set(organizing):
                print(f"- {a}")

        for a in set(organizing):
            self.wishes.remove(a)

        conflicting = [a for a in self.wishes
                       for (slot, available) in self.availability.items()
                       if a.overlaps(slot) and not available]
        if verbose and conflicting:
            print("Found wishes where not available :")
            for a in set(conflicting):
                print(f"- {a}")
        for a in set(conflicting):
            self.wishes.remove(a)

        # Blacklist constraint when the player does not want to play with an
        # organizer.
        blacklisted_wishes = []
        for w in self.wishes:
            blacklisted_orgas = set(self.blacklist[BlacklistKind.DONT_BE_ORGANIZED_BY])
            blacklisted_orgas &= set(w.orgas)
            if blacklisted_orgas:
                if verbose:
                    print(f'- Wish "{w}" removed because the game is organized '
                          f'by blacklisted organizers: {blacklisted_orgas}')
                blacklisted_wishes.append(w)
        for w in set(blacklisted_wishes):
            self.wishes.remove(w)

        # Blacklist constraints when an organizer does not want to play with a
        # player.
        blacklisted_wishes = []
        for w in self.wishes:
            blacklisting_orgas = [orga for orga in w.orgas
                                  if self in orga.blacklist[BlacklistKind.DONT_ORGANIZE_FOR]]
            if blacklisting_orgas:
                if verbose:
                    print(f'- Wish "{w}" removed because the game is organized '
                          f'by blacklisted organizers: {blacklisting_orgas}')
                blacklisted_wishes.append(w)
        for w in set(blacklisted_wishes):
            self.wishes.remove(w)

        # Clearing up activity names only to keep those where the player is
        # available:
        for w in self.wishes:
            if self.ranked_activity_names == [] or \
               self.ranked_activity_names[-1] != w.name:
                self.ranked_activity_names.append(w.name)

    def name_with_rank(self, name: str) -> str:
        """Return the name of an activity along with its rank.
        Contrary to the function "activity_coef", the rank is the rank of the
        activity among the initial wishlist, not among the wishlist after
        filtering out activities where the player is unavailable."""
        rank = 1 + self.initial_activity_names.index(name)
        return f"{name} (n°{rank})"

    def __repr__(self):
        return f"{self.id} | {self.name}"


def find_player_by_name(name: str, players: List[Player]) -> Optional[Player]:
    p = [pl for pl in players if pl.name == name]
    if not p:
        warn(f"Could not find player {name}")
        return None
    elif len(p) == 1:
        return p[0]
    else:
        raise ValueError(f"Several players corresponding to the name {name}")

# Extraction of data about availability
def get_available_players(
    players: List[Player],
    slot: TimeSlot,
    activity_name: Optional[str]) -> List[Player]:
    """Return the list of players available at a given time slot and an
    activity. If activity_name is None, returns every players available at that
    slot.

    slot: Must be one of the slots in the availabiilty
    """
    available = []
    for player in players:
        if not player.availability[slot]:
            # player is not available at this slot
            continue
        if activity_name is not None:
            if activity_name not in player.initial_activity_names:
                # player does not wish to play the activity
                continue

        available.append(player)

    return available

def print_dispos(players, activity_name: str, disp_available=False):
    slots = players[0].availability.keys()
    for slot in slots:
        pl = get_available_players(players, slot, activity_name)
        names = [p.name for p in pl]
        print(f"{slot}\t{len(pl)}\t")
        if disp_available:
            print(end="\t")
            print(*(p.name for p in pl), sep=", ")
