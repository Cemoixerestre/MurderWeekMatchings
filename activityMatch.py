from __future__ import annotations

from typing import List, Dict, Optional, Tuple, Iterator, Set
import datetime
from abc import ABCMeta, abstractmethod

from timeSlots import TimeSlot, generate_all_timeslots

class Activity:
    ACTIVE_ACTIVITIES = 0

    def __init__(self, name: str, capacity: int, start: datetime.datetime, end: datetime.datetime):
        # Auto number the activities
        self.id = Activity.ACTIVE_ACTIVITIES
        Activity.ACTIVE_ACTIVITIES += 1

        self.name: str = name
        self.capacity: int = capacity
        self.start: datetime.datetime = start
        self.end: datetime.datetime = end

        self.orgas: List[Player] = []
        self.players: List[Player] = []

    def __repr__(self):
        return f"{self.id} | {self.name} | {len(self.players)} / {self.capacity} players | {self.start} - {self.end}"

    def overlaps(self, start: datetime.datetime, end: datetime.datetime) -> bool:
        if (self.start <= start) and (start < self.end):
            return True
        elif (start <= self.start) and (self.start < end):
            return True
        else:
            return False

    def breaks_constraint(self, cast: List[Activity], constraint: Constraint) -> bool:
        if constraint == Constraint.TWO_SAME_DAY:
            return self.start.date() in [a.start.date() for a in cast]
        elif constraint == Constraint.NIGHT_THEN_MORNING:
            # Check if there is only a few hours between the murders but on different days
            pairs = [(self.end, a.start) for a in cast if self.end <= a.start] + \
                    [(a.end, self.start) for a in cast if a.end <= self.start]
            return any([(b - a <= datetime.timedelta(hours=12))
                        and (a.date() != b.date()) for (a, b) in pairs])
        elif constraint == Constraint.TWO_CONSECUTIVE_DAYS:
            return any([abs((a.start.date() - self.start.date()).days) == 1 for a in cast])
        elif constraint == Constraint.THREE_CONSECUTIVE_DAYS:
            days_played = set([a.start.date() for a in cast] + [self.start.date()])
            days_played = sorted(list(days_played))
            return any(((b - a).days == 1) and
                       ((c-b).days == 1) for (a, b, c) in window(days_played, 3))
        elif constraint == Constraint.MORE_CONSECUTIVE_DAYS:
            days_played = set([a.start.date() for a in cast] + [self.start.date()])
            days_played = sorted(list(days_played))
            return any(((b - a).days == 1) and
                       ((c - b).days == 1) and
                       ((d - c).days == 1) for (a, b, c, d) in window(days_played, 4))
        else:
            raise ValueError("Unknown Constraint")

        # If we gave a specific player, we need to check its custom constraints.

    #def find_conflicting_activities(self, activities: List[Activity], player: Optional[Player] = None) -> List[Activity]:
    #    return [a for a in activities if self.conflicts_with(a, player=player)]

    def is_full(self) -> bool:
        return len(self.players) >= self.capacity

    def add_player(self, player: Player) -> None:
        self.players.append(player)

    def add_orga(self, orga: Player) -> None:
        self.orgas.append(orga)

    def remove_player(self, player: Player) -> None:
        if player not in self.players:
            print(f"Can't remove player {player.name} from {self.name}. They were not selected to be part of it")
            return
        self.players.remove(player)

    def remaining_slots(self) -> int:
        return self.capacity - len(self.players)


def window(seq: List, n: int = 2) -> Iterator:
    return iter(seq[i: i + n] for i in range(len(seq) - n + 1))


class Constraint:
    TWO_SAME_DAY = 0
    NIGHT_THEN_MORNING = 1
    TWO_CONSECUTIVE_DAYS = 2
    THREE_CONSECUTIVE_DAYS = 3
    MORE_CONSECUTIVE_DAYS = 4

    NAMES = {
        "Jouer deux jeux dans la même journée": TWO_SAME_DAY,
        "Jouer un soir et le lendemain matin": NIGHT_THEN_MORNING,
        "Jouer deux jours consécutifs": TWO_CONSECUTIVE_DAYS,
        "Jouer trois jours consécutifs": THREE_CONSECUTIVE_DAYS,
        "Jouer plus de trois jours consécutifs": MORE_CONSECUTIVE_DAYS
    }

    REPR = ["2 same day", "night then morning", "2 consecutive days",
            "3 consecutive days", "> 3 consecutive days"]

# The datatype used to represent conflicts. The goal is to distinsguish
# different kinds of conflicts and to print them accordingly.
Conflict = Tuple[int, Optional[Constraint]]
# ORGANIZING_ACTIVITY: Conflict = (0, None)
OVERLAPPING_ACTIVITY: Conflict = (1, None)
def broken_constraint_conflict(constraint: Constraint) -> Conflict:
    return (2, constraint)
BLACKLIST: Conflict = (3, None)
FULL: Conflict = (4, None)

CONFLICT_NAMES = ["organizing", "overlapping", "constraint", "blacklist", "full"]
def conflict_repr(c: Conflict) -> str:
    data = [CONFLICT_NAMES[c[0]]]
    if c[1] is not None:
        data.append(Constraint.REPR[c[1]])

    return " - ".join(data)


class Player:
    ACTIVE_PLAYERS = 0

    def __init__(self, name: str,
                 wishes: List[Activity],
                 non_availabilities: List[TimeSlot],
                 max_activities: Optional[int] = None,
                 ideal_activities: Optional[int] = None,
                 constraints: Optional[Set[Constraint]] = None,
                 orga_player_same_day: bool = True):
        # Auto number the players
        self.id = Player.ACTIVE_PLAYERS
        Player.ACTIVE_PLAYERS += 1

        self.name = name
        self.wishes = wishes
        self.non_availability: List[TimeSlot] = non_availabilities
        self.max_activities = max_activities
        self.ideal_activities = ideal_activities
        self.constraints: Set[Constraint] = constraints if constraints is not None else set()
        self.orga_player_same_day = orga_player_same_day

        self.blacklist: List[Player] = []
        self.activities: List[Activity] = []
        self.organizing: List[Activity] = []

    def add_orga(self, activity: Activity) -> None:
        self.organizing.append(activity)

    def conflict_with(self, activity: Activity) -> Optional[Conflict]:
        """Returns true if there is any conflict between the player and the activity."""
        for c in self.constraints:
            if activity.breaks_constraint(self.activities, c):
                return broken_constraint_conflict(c)
        #if any(activity.overlaps(other.start, other.end) for other in self.organizing):
        #    return ORGANIZING_ACTIVITY
        if any(activity.overlaps(other.start, other.end) for other in self.activities):
            return OVERLAPPING_ACTIVITY
        elif any(p for p in activity.players if p in self.blacklist):
            return BLACKLIST
        elif activity.is_full():
            return FULL
        else:
            return None

    def filter_availability(self, verbose:bool = False) -> None:
        """Function called at the beginning to filter impossible wishes.

        It filters out wishes where the player in unavailable, when it
        overlaps with the organization of a game, or wishes the same day
        as an orginazition (when the player asked not to participate
        and organize the same day).

        This procedure is called once after the initialization of players
        and activities.
        """
        if not self.orga_player_same_day:
            activity_when_orga = [a for a in self.wishes for o in self.organizing
                                  if a.start.date() == o.start.date()]
            if verbose and activity_when_orga:
                print("Found wishes and activities the same day :")
                for a in set(activity_when_orga):
                    print(f"- {a}")

            for a in set(activity_when_orga):
                self.wishes.remove(a)

        organizing = [a for a in self.wishes for o in self.organizing
                       if a.overlaps(o.start, o.end)]
        if verbose and organizing:
            print("Found wishes when organizing :")
            for a in set(organizing):
                print(f"- {a}")

        for a in set(organizing):
            self.wishes.remove(a)


        conflicting = [a for a in self.wishes for slot in self.non_availability
                       if a.overlaps(slot.start, slot.end)]
        if verbose and conflicting:
            print("Found wishes where not available :")
            for a in set(conflicting):
                print(f"- {a}")

        for a in set(conflicting):
            self.wishes.remove(a)

    def update_wishlist(self, verbose:bool = False) -> None:
        """Remove impossible wishes.

        This corresponds to activities with a conflict (see the
        method `conflict_with` and full activities.

        This function is called after each attribution pass.
        """
        conflicts = [(a, self.conflict_with(a)) for a in self.wishes]
        conflicts = [(a, c) for (a, c) in conflicts if c is not None]
        if verbose and conflicts:
            print(f"Player {self.name}: removed conflicting wishes :")
            for (a, c) in conflicts:
                print(f"- {a} ({conflict_repr(c)})")
        for (a, _) in conflicts:
            self.wishes.remove(a)

    def __repr__(self):
        return f"{self.id} | {self.name}"

    def could_play(self, activity: Activity) -> bool:
        """TODO: rewrite, maybe reusing some code."""
        if (self.max_activities is not None) and (len(self.activities) >= self.max_activities):
            assert(len(self.activities == self.max_activities))
            return False

        #self.update_wishlist()
        #return activity in self.wishes

        return not(any(activity.overlaps(ts.start, ts.end) for ts in self.non_availability)
                   or self.conflict_with(activity) is not None)

    def remove_wish(self, activity: Activity) -> None:
        self.wishes = [a for a in self.wishes if a != activity]

    def remove_wishes_by_name(self, name: str) -> None:
        """Remove all wishes corresponding to some name."""
        self.wishes = [a for a in self.wishes if a.name != name]

    def has_wishes(self) -> bool:
        return len(self.wishes) > 0

    def is_satisfied(self) -> bool:
        """True if the player has at least the ideal number of activities."""
        return self.ideal_activities is not None and \
               len(self.activities) >= self.ideal_activities

    def add_activity(self, activity: Activity, verbose=False) -> None:
        self.activities.append(activity)
        self.remove_wishes_by_name(activity.name)

        # remove conflicting wishes
        # MOVED: activities are removed at the end of the assignation pass
        # self.update_wishlist(verbose=verbose)

        # If we reached the max number of activities, empty the wishlist
        if self.max_activities is not None and len(self.activities) >= self.max_activities:
            assert len(self.activities) == self.max_activities
            self.wishes = []

    def remove_activity(self, activity: Activity) -> None:
        if activity not in self.activities:
            print(f"Can't remove activity {activity.name} from {self.name}. "
                   "They were not selected to be part of it")
            return
        self.activities.remove(activity)

    def add_blacklist_player(self, player: Player) -> None:
        """Create a blacklist conflict between two players."""
        # The blacklist conflict is symmetrical. We don't care
        # who is blacklisting who, in the end, the only thing
        # that matters is that two players cannot play together.
        self.blacklist.append(player)
        player.blacklist.append(self)

    def is_last_chance(self):
        """If the player has not been cast yet and only one wish remains"""
        return (len(self.activities) == 0) and (len(self.wishes) == 1)

    def activity_rank(self, activity: Activity) -> int:
        return self.wishes.index(activity)

    def possible_wishes(self) -> List[Activity]:
        return self.wishes.copy()


class Matching(metaclass=ABCMeta):
    """An abstract manager for generating a matching.

    It manages the list of active players and activities. It can print
    information about the matching lists, the players lists, the availabilities
    of players, etc.

    In order to instantiate a matching class, you need to define an `assignation_pass`
    method. This method takes a list of players. It should returns a list of
    (player, activity) for each player that is going to be assigned an activity.

    Each of these players must be part of the player list. Each player must be
    assign at most one activity at each pass. It is possible (for the moment)
    that two players with a blacklist conflict are assign the same activity
    at some pass.

    Example:

    class MyMatching(Matching):
        def assignation_pass(self, players: List[Player], verbose: bool) -> List[Tuple[Player, Activity]]:
            # Define your assignation procedure here
            [...]

    Finally, the `solve` method resolve the matching. It repeatedly calls the
    `assignation pass` procedure. It removes conflicting activity after each
    assignation pass. It manages blacklist conflicts. Finally, when no
    more assignation can be performed, it terminates."""
    def __init__(self, players: List[Player], activities: List[Activity]):
        self.active_players = players
        self.active_activities = activities

        # Player with the ideal number of activities (but that could
        # still play other activities).
        self.satisfied_players: List[Player] = []
        # Player with the maximal number of activities, or that could not play
        # any other activity.
        self.done_players: List[Player] = []
        # Full activities.
        self.done_activities: List[Activity] = []

    def find_activity(self, id: int) -> Activity:
        return [a for a in self.active_activities + self.done_activities if a.id == id][0]

    def find_activity_by_name(self, name: str) -> List[Activity]:
        act = [a for a in self.active_activities + self.done_activities if a.name.lower() == name.lower()]
        if not act:
            raise ValueError(f"ERROR. Found no activity with name {name}")
        return act

    def all_players(self) -> List[Player]:
        return self.active_players + self.satisfied_players + self.done_players

    def find_player(self, id: int) -> Player:
        return [p for p in self.all_players() if p.id == id][0]

    def find_player_by_name(self, name: str) -> Player:
        pl = [p for p in self.all_players() if p.name.lower() == name.lower()]
        if not pl:
            raise ValueError(f"ERROR. Found no players with name {name}")
        return pl[0]

    def cleanup(self, verbose=False) -> None:
        # Find activities that are full
        full_activities = [a for a in self.active_activities if a.is_full()]
        # Remove them from the active list
        for a in full_activities:
            self.active_activities.remove(a)
            self.done_activities.append(a)

        # If a player has no more possible wishes, remove it
        removed = []
        for p in self.active_players:
            p.update_wishlist(verbose=verbose)
            if not p.has_wishes():
                removed.append(p)
                self.done_players.append(p)
            elif p.is_satisfied():
                removed.append(p)
                self.satisfied_players.append(p)
        self.active_players = [p for p in self.active_players
                               if p not in removed]

        removed = []
        for p in self.satisfied_players:
            p.update_wishlist(verbose=verbose)
            if not p.has_wishes():
                removed.append(p)
                self.done_players.append(p)
        self.satisfied_players = [p for p in self.satisfied_players
                                  if p not in removed]

    def assign_activity(self, player: Player, activity: Activity, verbose=False) -> None:
        # First check if activity has room left
        if activity.is_full():
            print(f"Tried to give [{activity.name}] to {player.name} but it is full.")
            return

        # Check potential blacklist conflicts with other players
        for p in player.blacklist:
            if p in activity.players:
                print(f"Could not give {activity.name} to {player.name} because of some blacklist conflict")
                return

        # Add the activity to the player cast list, and the player to the activity cast list
        print(f"Giving [{activity.name}] to {player.name}")
        player.add_activity(activity, verbose=verbose)
        activity.add_player(player)

    def _remove_from_activity(self, player: Player, activity: Activity) -> None:
        print(f"Removing {player.name} from the activity {activity.name}")
        player.remove_activity(activity)
        activity.remove_player(player)
        # The activity may now have available slots. So update it !
        if activity not in self.active_activities:
            self.done_activities.remove(activity)
            self.active_activities.append(activity)

    def remove_from_activity(self, player_name: str, activity_name: str) -> None:
        act = self.find_activity_by_name(activity_name)
        if len(act) != 1:
            print(f"Multiple activities have the name {activity_name}. Could not make the difference.")
            print("Instead, use `remove_from_activity_by_id(player, id)` with the unique activity ID")
            print(f"Activities that matched : ")
            for a in act:
                print(a)
            return
        self._remove_from_activity(self.find_player_by_name(player_name), act[0])

    def remove_from_activity_by_id(self, player_name: str, activity_id: int) -> None:
        self._remove_from_activity(self.find_player_by_name(player_name), self.find_activity(activity_id))

    def force_assign_activity(self, player_name: str, activity_name: str, verbose=False) -> None:
        act = self.find_activity_by_name(activity_name)
        if len(act) != 1:
            print(f"Multiple activities have the name {activity_name}. Could not make the difference.")
            print("Instead, use `force_assign_activity_by_id(player, id)` with the unique activity ID")
            print(f"Activities that matched : ")
            for a in act:
                print(a)
            return

        self.assign_activity(self.find_player_by_name(player_name), act[0], verbose=verbose)

    def force_assign_activity_by_id(self, player_name: str, activity_id: int, verbose=False) -> None:
        self.assign_activity(self.find_player_by_name(player_name),
                             self.find_activity(activity_id), verbose=verbose)

    def print_activities_status(self) -> None:
        print("Activities with a full cast:")
        self.done_activities.sort(key=lambda a: a.id)
        for a in self.done_activities:
            print(f"* {a}")
            for p in a.players:
                print(f"  - {p.name}")
            print("")

        print("Activities WITHOUT a full cast:")
        self.active_activities.sort(key=lambda a: a.id)
        for a in self.active_activities:
            print(f"* {a}")
            for p in a.players:
                print(f"  - {p.name}")
            print(f" Missing {a.remaining_slots()} more")
            print("")

    def print_players_status(self) -> None:
        print("Activities given to each player:")
        players = self.all_players()
        players.sort(key=lambda p: p.name)

        less = 0 # number of players with less activities than ideal
        ideal = 0 # number of players with the ideal number of activities
        more = 0 # number of players with more activities than ideal
        no_ideal = 0
        for p in players:
            print(f"* {p.name} | Got {len(p.activities)} activities. "
                  f"Ideal {p.ideal_activities}. Max {p.max_activities}.")
            print("  + Activities")
            p.activities.sort(key=lambda a: a.start)
            for a in p.activities:
                print(f"    - {a.name} | Start: {a.start}")
            if p.organizing:
                print("  + Also organizing the following activities:")
                for a in p.organizing:
                    print(f"    - {a.name} | Start: {a.start}")
            if p.ideal_activities is None:
                no_ideal += 1
            elif len(p.activities) < p.ideal_activities:
                less += 1
            elif len(p.activities) == p.ideal_activities:
                ideal += 1
            else:
                more += 1

        nb_players = len(self.active_players) + len(self.done_players)
        print( "Players with less activities than ideal:\t"
              f"{less} (= {100 * less / nb_players:.1f}%)")
        print( "Players with ideal number of activities:\t"
              f"{ideal} (= {100 * ideal / nb_players:.1f}%)")
        print( "Players with more activities than ideal:\t"
              f"{more} (= {100 * more / nb_players:.1f}%)")
        print( "Players with no ideal number of activities:\t"
              f"{no_ideal} (= {100 * no_ideal / nb_players:.1f}%)")

    @abstractmethod
    def assignation_pass(self, players: List[Player], verbose=False) -> Dict[Player, Activity]:
        pass

    def solve(self, verbose=False) -> None:
        nb_pass = 0
        while True:
            print(f"\nPass {nb_pass}")
            nb_pass += 1
            assignation = self.assignation_pass(self.active_players, verbose=verbose)
            if assignation == []:
                break
            for (player, activity) in assignation:
                self.assign_activity(player, activity, verbose=verbose)
            self.cleanup(verbose=verbose)

        while True:
            print(f"\nPass {nb_pass}: trying to fill the last activities "
                   "with satisfied players.")
            if verbose:
                names = [p.name for p in self.satisfied_players]
                print("Last players:", "; ".join(names))
            nb_pass += 1
            assignation = self.assignation_pass(self.satisfied_players, verbose=verbose)
            if assignation == []:
                break
            for (player, activity) in assignation:
                self.assign_activity(player, activity, verbose=verbose)
            self.cleanup(verbose=verbose)
        print("Done")

    def print_available_players(self) -> None:
        slots = generate_all_timeslots()
        for s in slots:
            dummy_activity = Activity(f"{s}", 1000, s.start, s.end)
            potential_players = [p for p in self.active_players + self.done_players
                                 if p.could_play(dummy_activity)]
            print(f"{s},{','.join([p.name for p in potential_players])}")
