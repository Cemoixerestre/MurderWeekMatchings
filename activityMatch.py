from __future__ import annotations

from typing import List, Dict, Optional, Tuple, Iterator, Set
from datetime import datetime, timedelta
from collections import defaultdict
from itertools import combinations, product
import csv
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
        self.timeslot = TimeSlot(None, start, end)
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
        return self.timeslot.start.date()

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

CONSTRAINT_NAMES = {
    "Jouer deux jeux dans la même journée": TWO_SAME_DAY,
    "Jouer un soir et le lendemain matin": NIGHT_THEN_MORNING,
    "Jouer deux jours consécutifs": TWO_CONSECUTIVE_DAYS,
    "Jouer trois jours consécutifs": THREE_CONSECUTIVE_DAYS,
    "Jouer plus de trois jours consécutifs": MORE_CONSECUTIVE_DAYS
}

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
        self.ranked_activity_names: List[str] = []
        self.non_availability: List[TimeSlot] = non_availabilities
        self.max_activities = max_activities
        self.ideal_activities = ideal_activities
        assert ideal_activities <= max_activities, \
               f"Player {name}: the number of ideal activities is larger " \
               f"than the maximal number of activities."
        self.constraints: Set[Constraint] = constraints if constraints is not None else set()
        self.orga_player_same_day = orga_player_same_day
        # A ILP variable representing the number of activities of the player.
        # It is bounded first by the ideal number of activities, then by the
        # maximal number of activities.
        self.nb_activites: Option[Var] = None

        self.blacklist: List[Player] = []
        self.organizing: List[Activity] = []

    def add_orga(self, activity: Activity) -> None:
        self.organizing.append(activity)

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
                                  if a.date() == o.date()]
            if verbose and activity_when_orga:
                print("Found wishes and activities the same day :")
                for a in set(activity_when_orga):
                    print(f"- {a}")

            for a in set(activity_when_orga):
                self.wishes.remove(a)

        organizing = [a for a in self.wishes for o in self.organizing
                       if a.overlaps(o.timeslot)]
        if verbose and organizing:
            print("Found wishes when organizing :")
            for a in set(organizing):
                print(f"- {a}")

        for a in set(organizing):
            self.wishes.remove(a)

        conflicting = [a for a in self.wishes for slot in self.non_availability
                       if a.overlaps(slot)]
        if verbose and conflicting:
            print("Found wishes where not available :")
            for a in set(conflicting):
                print(f"- {a}")
        for a in set(conflicting):
            self.wishes.remove(a)

        for w in self.wishes:
            if self.ranked_activity_names == [] or \
               self.ranked_activity_names[-1] != w.name:
                self.ranked_activity_names.append(w.name)

    def create_nb_activities_variable(self, model: Model) -> None:
        self.nb_activities = model.add_var(var_type=INTEGER,
                                           ub=self.ideal_activities)

    def activity_coef(self, activity: str, decay: float) -> float:
        return decay ** self.ranked_activity_names.index(activity.name)

    def __repr__(self):
        return f"{self.id} | {self.name}"

    def add_blacklist_player(self, player: Player) -> None:
        """Create a blacklist conflict between two players."""
        self.blacklist.append(player)


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
            for q in p.blacklist:
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

class MatchResult:
    def __init__(self, players: List[Player], activities: List[Activity]):
        # List of players for each activity
        self.players: Dict[Activity, List[Player]] = \
            {a:[] for a in activities}
        # List of activities for each player
        self.activities: Dict[Player, List[Activity]] = \
            {a:[] for a in players}
        self.nb_players = len(players)
        self.nb_activities = len(activities)
        # Number of remaining slots for each activities
        self.remaining_slots: Dict[Activity, int] = \
            {a:a.capacity for a, ps in self.players.items()}

    def add(self, player: Player, activity: Activity) -> None:
        self.activities[player].append(activity)
        self.players[activity].append(player)
        self.remaining_slots[activity] -= 1
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
            if p.ranked_activity_names[0] not in activity_names:
                no_best_choice.append(p)
            for name in p.ranked_activity_names[:3]:
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
        print(f"Successfully write to the file {filename}")
