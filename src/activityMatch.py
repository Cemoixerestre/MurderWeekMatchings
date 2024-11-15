from __future__ import annotations

from typing import List, Dict, Optional, Tuple, Iterator, Set
from datetime import datetime, timedelta
from collections import defaultdict
from itertools import combinations, product
import csv
from warnings import warn
from mip import Model, Var, OptimizationStatus, maximize, xsum, BINARY, INTEGER

from timeslots import TimeSlot

class Activity:
    ACTIVE_ACTIVITIES = 0

    def __init__(
            self,
            name: str,
            capacity: int,
            start: datetime,
            end: datetime
        ):
        # Auto number the activities
        self.id = Activity.ACTIVE_ACTIVITIES
        Activity.ACTIVE_ACTIVITIES += 1

        self.name: str = name
        self.capacity: int = capacity
        self.timeslot = TimeSlot(start, end)
        # An ILP variable representing the number of players playing the
        # activity. It is bounded by the capacity.
        self.nb_players: Option[Var] = None

        self.orgas: List[Player] = []

    def create_nb_players_variable(self, model: Model) -> None:
        self.nb_players = model.add_var(var_type=INTEGER, ub=self.capacity)

    def __repr__(self):
        return f"{self.id} | {self.name} | " \
               f"{self.timeslot}"
               #f"{len(self.players)} / {self.capacity} players | " 

    def is_full(self) -> bool:
        return len(self.players) >= self.capacity

    def add_player(self, player: Player) -> None:
        self.players.append(player)

    def add_orga(self, orga: Player) -> None:
        self.orgas.append(orga)

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


# Constraint management
TWO_SAME_DAY = 0
NIGHT_THEN_MORNING = 1
TWO_CONSECUTIVE_DAYS = 2
THREE_CONSECUTIVE_DAYS = 3
MORE_CONSECUTIVE_DAYS = 4
PLAY_ORGA_SAME_DAY = 5
PLAY_ORGA_TWO_CONSECUTIVE_DAYS = 6

# TODO: treat "play and organize the same day" like other constraints.
CONSTRAINT_NAMES = {
    "Jouer deux jeux dans la même journée": TWO_SAME_DAY,
    "Jouer un soir et le lendemain matin": NIGHT_THEN_MORNING,
    "Jouer deux jours consécutifs": TWO_CONSECUTIVE_DAYS,
    "Jouer trois jours consécutifs": THREE_CONSECUTIVE_DAYS,
    "Jouer plus de trois jours consécutifs": MORE_CONSECUTIVE_DAYS,
    "Jouer et (co-)organiser dans la même journée": PLAY_ORGA_SAME_DAY,
    "Jouer et (co-)organiser deux jours consécutifs":
        PLAY_ORGA_TWO_CONSECUTIVE_DAYS
}

# Blacklists management
# TODO: create a type alias for blacklist kinds, for example with an
# enumeration?
DONT_PLAY_WITH = 0
DONT_ORGANIZE_FOR = 1
DONT_BE_ORGANIZED_BY = 2

BLACKLIST_KINDS = {
    "Ne pas jouer avec": DONT_PLAY_WITH,
    "Ne pas organiser pour": DONT_ORGANIZE_FOR,
    "Ne pas être organisée par": DONT_BE_ORGANIZED_BY
}

class Player:
    ACTIVE_PLAYERS = 0

    def __init__(self, name: str,
                 initial_activity_names: List[Activity],
                 availabilities: Dict[TimeSlot, bool],
                 max_activities: Optional[int] = None,
                 ideal_activities: Optional[int] = None,
                 constraints: Optional[Set[Constraint]] = None):
        # Auto number the players
        # Note: not used anymore, could be deleted.
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
        self.constraints: Set[Constraint] = constraints if constraints is not None else set()
        # A ILP variable representing the number of activities of the player.
        # It is bounded first by the ideal number of activities, then by the
        # maximal number of activities.
        self.nb_activites: Option[Var] = None

        self.blacklist: Dict[int, Set[Player]] = \
                        {bl_kind:set() for bl_kind in BLACKLIST_KINDS.values()}
        self.organizing: List[Activity] = []

    def add_orga(self, activity: Activity) -> None:
        self.organizing.append(activity)

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

    def filter_availability(self, verbose:bool = False) -> None:
        """Function called at the beginning to filter impossible wishes.

        It filters out wishes where the player in unavailable, when it
        overlaps with the organization of a game, or wishes the same day
        as an orginazition (when the player asked not to participate
        and organize the same day).

        This procedure is called once after the initialization of players
        and activities.
        """
        if PLAY_ORGA_SAME_DAY in self.constraints:
            activity_when_orga = [a for a in self.wishes for o in self.organizing
                                  if a.date() == o.date()]
            if verbose and activity_when_orga:
                print("Found wishes and activities the same day :")
                for a in set(activity_when_orga):
                    print(f"- {a}")

            for a in set(activity_when_orga):
                self.wishes.remove(a)

        if PLAY_ORGA_TWO_CONSECUTIVE_DAYS in self.constraints:
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
            blacklisted_orgas = set(self.blacklist[DONT_BE_ORGANIZED_BY])
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
                                  if self in orga.blacklist[DONT_ORGANIZE_FOR]]
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

    def create_nb_activities_variable(self, model: Model) -> None:
        self.nb_activities = model.add_var(var_type=INTEGER,
                                           ub=self.ideal_activities)

    def activity_coef(self, activity: str, decay: float) -> float:
        return decay ** self.ranked_activity_names.index(activity.name)

    def name_with_rank(self, name: str) -> str:
        """Return the name of an activity along with its rank.
        Contrary to the function "activity_coef", the rank is the rank of the
        activity among the initial wishlist, not among the wishlist after
        filtering out activities where the player is unavailable."""
        rank = 1 + self.initial_activity_names.index(name)
        return f"{name} (n°{rank})"

    def __repr__(self):
        return f"{self.id} | {self.name}"

    def add_blacklist_players(self, players: Player, bl_kind: int) -> None:
        """Create a blacklit conflict between two players."""
        self.blacklist[bl_kind].add(players)


# Extraction of data about availability
def get_available_players(
    players: List[Player],
    slot: TimeSlot,
    activity_name: Option[str]) -> List[Player]:
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


class Matcher:
    """TODO"""
    def __init__(self, players: List[Player], activities: List[Activity],
                 decay=0.5):
        self.players = players
        self.players.sort(key=lambda p: p.name)
        self.activities = activities
        self.model = Model()
        self.vars: Dict[Tuple(Player, Activity), Var] = {}
        self.decay = decay

        for p in self.players:
            p.create_nb_activities_variable(self.model)
            for a in p.wishes:
                self.vars[p, a] = self.model.add_var(var_type=BINARY)

        for a in self.activities:
            a.create_nb_players_variable(self.model)

        self.generate_model()

    def generate_model(self) -> None:
        """Fill the model with the constraints."""
        # nb_activities variables are the sum of activities
        for p in self.players:
            acts_with_p = [v for (q, _), v in self.vars.items() if p is q]
            self.model += xsum(acts_with_p) == p.nb_activities

        # nb_players variables are the sum of activities
        for a in self.activities:
            players_with_a = [v for (_, b), v in self.vars.items() if a is b]
            self.model += xsum(players_with_a) == a.nb_players
            
        # A player cannot play two sessions of the same game:
        for p in self.players:
            wishes_by_name = defaultdict(list)
            for w in p.wishes:
                wishes_by_name[w.name].append(w)
            for wishes_same_name in wishes_by_name.values():
                if len(wishes_same_name) >= 2:
                    c = xsum(self.vars[p, a] for a in wishes_same_name) <= 1
                    self.model += c

        # Time constaints:
        for p in self.players:
            activities_by_days = defaultdict(list)
            for act in p.wishes:
                activities_by_days[act.date()].append(act)
            days_played = list(activities_by_days.keys())

            one_day = timedelta(days=1)

            if TWO_SAME_DAY in p.constraints:
                for acts_same_day in activities_by_days.values():
                    c = xsum(self.vars[p, a] for a in acts_same_day) <= 1
                    self.model += c
            else:
                # In any cases, a player cannot play two activities at the
                # same time.
                for acts_same_day in activities_by_days.values():
                    for a, b in combinations(acts_same_day, 2):
                        if a.overlaps(b.timeslot):
                            self.model += self.vars[p, a] + self.vars[p, b] <= 1

            if TWO_CONSECUTIVE_DAYS in p.constraints:
                for day in days_played:
                    for a, b in product(activities_by_days[day],
                                        activities_by_days[day + one_day]):
                        self.model += self.vars[p, a] + self.vars[p, b] <= 1

            if THREE_CONSECUTIVE_DAYS in p.constraints:
                for day in days_played:
                    for acts in product(activities_by_days[day],
                                        activities_by_days[day + one_day],
                                        activities_by_days[day + 2 * one_day]):
                        self.model += xsum(self.vars[p, a] for a in acts) <= 2

            if MORE_CONSECUTIVE_DAYS in p.constraints:
                for day in days_played:
                    for acts in product(activities_by_days[day],
                                        activities_by_days[day + one_day],
                                        activities_by_days[day + 2 * one_day],
                                        activities_by_days[day + 3 * one_day]):
                        self.model += xsum(self.vars[p, a] for a in acts) <= 3

            if NIGHT_THEN_MORNING in p.constraints:
                for day in days_played:
                    for a, b in product(activities_by_days[day],
                                        activities_by_days[day + one_day]):
                        if a.night_then_morning(b):
                            self.model += self.vars[p, a] + self.vars[p, b] <= 1
            
        # Blacklist constraints:
        for p in self.players:
            for q in p.blacklist[DONT_PLAY_WITH]:
                for a in self.activities:
                    if a in p.wishes and a in q.wishes:
                        self.model += self.vars[p, a] + self.vars[q, a] <= 1

        # Finally, the function to optimize:
        obj = maximize(xsum(p.activity_coef(a, self.decay) * v
                            for (p, a), v in self.vars.items()))
        self.model.objective = obj

    def find_activity(self, id: int) -> Activity:
        """Find an activity using an ID"""
        return [a for a in self.activities if a.id == id][0]

    def find_activity_by_name(self, name: str) -> List[Activity]:
        act = [a for a in self.activities if a.name.lower() == name.lower()]
        if not act:
            raise ValueError(f"ERROR. Found no activity with name {name}")
        return act

    def find_player(self, id: int) -> Player:
        return [p for p in self.players if p.id == id][0]

    def find_player_by_name(self, name: str) -> Player:
        pl = [p for p in self.players if p.name.lower() == name.lower()]
        if not pl:
            raise ValueError(f"ERROR. Found no players with name {name}")
        return pl[0]

    def force_assign_activity(
            self,
            player_name: str,
            activity_name: str
        ) -> None:        
        """Force the assignement of a player to an activity. This method must
        be called *before* the methode `solve`, otherwise it is useless. May
        fail if several activities correspond to the name."""
        player = self.find_player_by_name(player_name)
        act = [a for a in player.wishes if a.name == activity_name]
        if act == []:
            raise ValueError(f"No activity named {activity_name} that "
                             f"{player_name} can play.")
        if len(act) != 1:
            print(f"Multiple activities have the name {activity_name}. "
                  f"We will make sure that the player {player_name} is "
                   "affected to one of those. If you want to assign "
                  f"{player_name} to a particular activity, you should use the "
                   "method `force_assign_activity_by_id`.")

        self.model += xsum(self.vars[player, a] for a in act) >= 1

    def force_assign_activity_by_id(
            self, 
            player_name: str, 
            activity_id: int
        ) -> None:
        """force the assignement of a player to an activity. This method must
        be called *before* the method `solve`, otherwise its effect on the
        assignation is not visible."""
        player = self.find_player_by_name(player_name)
        activity = self.find_activity(activity_id)
        self.vars[player, activity].lb = 1

    def set_min_players_activity_by_name(
            self,
            activity_name: str,
            min_number: Option[Int]=None
        ) -> None:
        """Set the minimal number of players for an activity to a given
        number. If no number is provided, set the minimal number of players to
        the capacity of the activity. This method must be called *before* the
        method `solve`, otherwise its effect on the assignation is not visible.
        """
        act = self.find_activity_by_name(activity_name)
        if len(act) != 1:
            print(f"Multiple activities have the name {activity_name}. Could not make the difference.")
            print("Instead, use `force_assign_activity_by_id(player, id)` with the unique activity ID")
            print(f"Activities that matched : ")
            for a in act:
                print(a)
            raise ValueError

        if min_number is None:
            min_number = act[0].capacity
        act[0].nb_players.lb = min_number
        print(f"Minimal number of players set to {min_number}")

    def solve(self, verbose=False) -> MatchResult:
        # Finding a solution where every player plays at most the *ideal* number
        # of games.
        status = self.model.optimize()
        if status != OptimizationStatus.OPTIMAL:
            print(status)
            raise RuntimeError("Error while solving the problem. Maybe the "
                               "constraints where unsatisfiable?")

        # We want to improve the obtained solution so that each player can play
        # up to the maximal number of games.
        # But first, we are going to set the found solution in stone so that a
        # player `p` that was assigned an activity `a` is still assigned that
        # activity.
        for v in self.vars.values():
            v.lb = v.x

        # Then, we are going to increase the limits for the number of activity.
        for p in self.players:
            p.nb_activities.ub = p.max_activities

        self.model.optimize()
        res = MatchResult(self.players, self.activities)
        for (p, a), v in self.vars.items():
            if v.x >= 0.9:
                res.add(p, a)
        return res
    
    def add_players(self, act_id: int, players: str) -> None:
        activity = self.find_activity(act_id)
        for name in players.split('\n'):
            if name == '':
                continue
            player = self.find_player_by_name(name)
            if (player, activity) not in self.vars:
                warn(f"{name} is not playing {activity}")
                continue
            self.vars[player, activity].lb = 1
        print("Players successfully added")
    
    def raise_player_nb_activities(self, name: str, nb: int) -> None:
        player = self.find_player_by_name(name)
        assert player.ideal_activities <= nb <= player.max_activities
        player.nb_activities.ub = nb

class MatchResult:
    def __init__(self, players: List[Player], activities: List[Activity]):
        # List of players for each activity
        self.players: Dict[Activity, List[Player]] = \
            {a:[] for a in activities}
        # List of activities for each player
        self.activities: Dict[Player, List[Activity]] = \
            {p:[] for p in players}
        self.refused: Dict[Player, List[str]] = \
            {p: p.ranked_activity_names.copy() for p in players}
        self.unavailable: Dict[Player, List[str]] = \
            {p:list(set(p.initial_activity_names) - set(p.ranked_activity_names))
             for p in players}
        
        self.nb_players = len(players)
        self.nb_activities = len(activities)
        # Number of remaining slots for each activities
        self.remaining_slots: Dict[Activity, int] = \
            {a:a.capacity for a, ps in self.players.items()}

    def add(self, player: Player, activity: Activity) -> None:
        self.activities[player].append(activity)
        self.players[activity].append(player)
        self.remaining_slots[activity] -= 1
        self.refused[player].remove(activity.name)
        assert self.remaining_slots[activity] >= 0

    def print_activities_status(self) -> None:
        print("Activities with a full cast:")
        for a, ps in self.players.items():
            if self.remaining_slots[a] > 0:
                # The activity is not full
                continue
            print(f"* {a}")
            for p in ps:
                print(f"  - {p.name}")
            print("")

        print("Activities WITHOUT a full cast:")
        for a, ps in self.players.items():
            if self.remaining_slots[a] == 0:
                # The activity is not full
                continue
            print(f"* {a}")
            for p in ps:
                print(f"  - {p.name}")
            print(f" Missing {self.remaining_slots[a]} more")
            print("")

    def print_players_status(self) -> None:
        print("Activities given to each player:")
        less = 0 # number of players with less activities than ideal
        ideal = 0 # number of players with the ideal number of activities
        more = 0 # number of players with more activities than ideal
        no_best_choice = [] # players who did not obtain their best choice
        top_3_choice = 0 # number of top 3 choices cumulated
        for (p, act) in self.activities.items():
            print(f"* {p.name} | Got {len(act)} activities. "
                  f"Ideal {p.ideal_activities}. Max {p.max_activities}.")
            print("  + Activities")
            act.sort(key=lambda a: a.timeslot.start)
            for a in act:
                print(f"    - {a.name} | {a.timeslot}")
            if p.organizing:
                print("  + Also organizing the following activities:")
                for a in p.organizing:
                    print(f"    - {a.name} | {a.timeslot}")

            # Collecting statistics
            if len(act) < p.ideal_activities:
                less += 1
            elif len(act) == p.ideal_activities:
                ideal += 1
            else:
                more += 1
            activity_names = [a.name for a in act]
            if p.initial_activity_names != [] and p.initial_activity_names[0] not in activity_names:
                no_best_choice.append(p)
            for name in p.initial_activity_names[:3]:
                if name in activity_names:
                    top_3_choice += 1

        print( "Players with less activities than ideal:\t"
              f"{less} (= {100 * less / self.nb_players:.1f}%)")
        print( "Players with ideal number of activities:\t"
              f"{ideal} (= {100 * ideal / self.nb_players:.1f}%)")
        print( "Players with more activities than ideal:\t"
              f"{more} (= {100 * more / self.nb_players:.1f}%)")
        print()
        print( "Players who did not obtain their best choice: "
              f"{' '.join(map(repr, no_best_choice))}")
        print(f"Nb of top 3 choices: {top_3_choice}")

    def export_activities_to_csv(self, filename: str) -> None:
        activities = sorted(self.players.keys(), key=lambda a: a.timeslot.start)
        max_orgas = max(len(a.orgas) for a in activities)
        max_players = max(len(ps) + 1 for ps in self.players.values())
        with open(filename, "w") as f:
            writer = csv.writer(f)
            writer.writerow(["Jeu"] + [a.name for a in activities])
            writer.writerow(["Jour"] + [a.timeslot.disp_day() for a in activities])
            writer.writerow(["Horaire"] + [a.timeslot.disp_hour() for a in activities])
            writer.writerow([])

            row_name = "Organisateurices"
            for i in range(max_orgas):
                orgas = [a.orgas[i].name if i < len(a.orgas) else ""
                         for a in activities]
                writer.writerow([row_name] + orgas)
                row_name = ""
            writer.writerow([])

            row_name = "Joueureuses"
            for i in range(max_players):
                players = []
                for a in activities:
                    remaining = self.remaining_slots[a]
                    if i < len(self.players[a]):
                        players.append(self.players[a][i].name)
                    elif i == len(self.players[a]) and remaining > 0:
                        players.append(f"... {remaining} places restantes")
                    else:
                        players.append("")
                writer.writerow([row_name] + players)
                row_name = ""
        print(f"Successfully wrote to the file {filename}")

    def write_activities_to_csv(self,
                                writer: csv.writer,
                                players: List[Player],
                                row_name: str,
                                activities: Dict[Player, List[Activity]],
                                disp_dates=True,
                                disp_rank=True) -> None:
        max_activities = max(len(act) for act in activities.values())
        for i in range(max_activities):
            row = [row_name]
            row_name = ""
            for p in players:
                if i >= len(activities[p]):
                    row.append("")
                    if disp_dates:
                        row.append("")
                    continue

                a = activities[p][i]
                if disp_rank:
                    row.append(p.name_with_rank(a.name))
                else:
                    row.append(a.name)
                if disp_dates:
                    row.append(repr(a.timeslot))

            writer.writerow(row)

    def write_names_to_csv(self,
                           writer: csv.writer,
                           players: List[Player],
                           row_name: str,
                           names: Dict[Player, List[str]],
                           disp_dates=True,
                           disp_rank=True) -> None:
        max_names = max(len(ns) for ns in names.values())
        for i in range(max_names):
            row = [row_name]
            row_name = ""
            for p in players:
                if i >= len(names[p]):
                    row.append("")
                    if disp_dates:
                        row.append("")
                    continue
                name = names[p][i]
                if disp_rank:
                    row.append(p.name_with_rank(name))
                else:
                    row.append(name)
                if disp_dates:
                    row.append("")

            writer.writerow(row)

    def export_players_to_csv(self,
                              filename: str,
                              disp_orga=True,
                              disp_refused=True,
                              disp_unavailable=True,
                              disp_dates=True,
                              disp_rank=True) -> None:
        players = sorted(self.activities.keys(), key=lambda p: p.name)
        for act in self.activities.values():
            act.sort(key=lambda a: a.timeslot.start)

        with open(filename, "w") as f:
            writer = csv.writer(f)
            row = ["Joueureuses"]
            for p in players:
                row.append(p.name)
                if disp_dates:
                    row.append("")
            writer.writerow(row)
            
            row = ["Nombre d'activités"]
            for p in players:
                row.append(f"{len(self.activities[p])}/{p.ideal_activities}, "
                           f"max={p.max_activities}")
                if disp_dates:
                    row.append("")
            writer.writerow(row)
            writer.writerow([])
            
            self.write_activities_to_csv(writer, players, "Activités",
                                         self.activities, disp_dates, disp_rank)
            if disp_orga:
                writer.writerow([])
                organizing = {p:p.organizing for p in players}
                self.write_activities_to_csv(writer, players, "Organise",
                                             organizing, disp_dates, disp_rank=False)
            if disp_refused:
                writer.writerow([])
                self.write_names_to_csv(writer, players, "N'a pas été pris·e à",
                                        self.refused, disp_dates, disp_rank)
            if disp_unavailable:
                writer.writerow([])
                self.write_names_to_csv(writer, players, "Indisponibilités",
                                        self.unavailable, disp_dates, disp_rank)
        print(f"Successfully wrote to the file {filename}")

    def compare(self, other: MatchResult):
        """Affiche les différences entre deux castings"""
        for a, ps in self.players.items():
            diff_plus = set(ps) - set(other.players[a])
            diff_minus = set(other.players[a]) - set(ps)
            if len(diff_plus) == 0 and len(diff_minus) == 0:
                continue
            print(a)
            for p in diff_plus:
                print(f"+ {p}")
            for p in diff_minus:
                print(f"- {p}")
            print()
