from __future__ import annotations

from typing import List, Dict, Tuple, Optional
from collections.abc import Callable
from itertools import combinations, product
from collections import defaultdict
from datetime import timedelta
from mip import Model, Var, OptimizationStatus, maximize, xsum, BINARY, INTEGER

from base import Activity, Player, Constraints, BlacklistKind
from match_result import MatchResult

def exponential_coef(decay: float) -> Callable([int], float):
    def coef(i): return decay ** i
    return coef

def hyperbolic_coef(i : int) -> float:
    return 1 / (i + 1.01)

EPSILON = 1 / 64

class Matcher:
    """TODO"""
    def __init__(self, players: List[Player], activities: List[Activity],
                 coef: Callable([int], float)=hyperbolic_coef):
        self.players = players
        self.players.sort(key=lambda p: p.name)
        self.activities = activities
        self.model = Model()
        # self.vars[p, a]: 1 iff the player p plays the activity a
        self.plays: Dict[Tuple(Player, Activity), Var] = {}
        # Let's assume that the player p wants an ideal number "i" activities
        # and a maximal number "m" of activities, with i <= m. We're going to
        # give a higher weight for only i activities and a lower weight
        # for the other activities.
        # This variable is 1 if p plays an activity a that's among the first i
        # activities.
        self.ideal_plays: Dict[Tuple(Player, Activity), Var] = {}
        self.coef = coef

        for p in self.players:
            for a in p.wishes:
                self.plays[p, a] = self.model.add_var(var_type=BINARY)
                self.ideal_plays[p, a] = self.model.add_var(var_type=BINARY)

        self.generate_model()

    def generate_model(self) -> None:
        """Fill the model with the constraints."""
        # An activity a played in the "ideal number of activities" is an activity played.
        for p, a in self.plays.keys():
            self.model += self.ideal_plays[p, a] <= self.plays[p, a]

        # nb_activities variables are the sum of activities
        for p in self.players:
            acts_with_p = [v for (q, _), v in self.plays.items() if p is q]
            ideal_acts_with_p = [v for (q, _), v in self.ideal_plays.items() if p is q]
            self.model += xsum(acts_with_p) <= p.max_activities
            self.model += xsum(ideal_acts_with_p) <= p.ideal_activities

        # The number of players is limited by the capacity
        for a in self.activities:
            players_with_a = [v for (_, b), v in self.plays.items() if a is b]
            self.model += xsum(players_with_a) <= a.capacity
           
        # A player cannot play two sessions of the same game:
        for p in self.players:
            wishes_by_name = defaultdict(list)
            for w in p.wishes:
                wishes_by_name[w.name].append(w)
            for wishes_same_name in wishes_by_name.values():
                if len(wishes_same_name) >= 2:
                    c = xsum(self.plays[p, a] for a in wishes_same_name) <= 1
                    self.model += c

        # Time constaints:
        for p in self.players:
            activities_by_days = defaultdict(list)
            for act in p.wishes:
                activities_by_days[act.date()].append(act)
            days_played = list(activities_by_days.keys())

            one_day = timedelta(days=1)

            if Constraints.TWO_SAME_DAY in p.constraints:
                for acts_same_day in activities_by_days.values():
                    c = xsum(self.plays[p, a] for a in acts_same_day) <= 1
                    self.model += c
            else:
                # In any cases, a player cannot play two activities at the
                # same time.
                for acts_same_day in activities_by_days.values():
                    for a, b in combinations(acts_same_day, 2):
                        if a.overlaps(b.timeslot):
                            self.model += self.plays[p, a] + self.plays[p, b] <= 1

            if Constraints.TWO_CONSECUTIVE_DAYS in p.constraints:
                for day in days_played:
                    for a, b in product(activities_by_days[day],
                                        activities_by_days[day + one_day]):
                        self.model += self.plays[p, a] + self.plays[p, b] <= 1

            if Constraints.THREE_CONSECUTIVE_DAYS in p.constraints:
                for day in days_played:
                    for acts in product(activities_by_days[day],
                                        activities_by_days[day + one_day],
                                        activities_by_days[day + 2 * one_day]):
                        self.model += xsum(self.plays[p, a] for a in acts) <= 2

            if Constraints.MORE_CONSECUTIVE_DAYS in p.constraints:
                for day in days_played:
                    for acts in product(activities_by_days[day],
                                        activities_by_days[day + one_day],
                                        activities_by_days[day + 2 * one_day],
                                        activities_by_days[day + 3 * one_day]):
                        self.model += xsum(self.plays[p, a] for a in acts) <= 3

            if Constraints.NIGHT_THEN_MORNING in p.constraints:
                for day in days_played:
                    for a, b in product(activities_by_days[day],
                                        activities_by_days[day + one_day]):
                        if a.night_then_morning(b):
                            self.model += self.plays[p, a] + self.plays[p, b] <= 1
           
        # Blacklist constraints:
        for p in self.players:
            for q in p.blacklist[BlacklistKind.DONT_PLAY_WITH]:
                for a in self.activities:
                    if a in p.wishes and a in q.wishes:
                        self.model += self.plays[p, a] + self.plays[q, a] <= 1

        # Finally, the function to optimize:
        obj: List[Tuple[float, Var]] = []
        for p, a in self.plays.keys():
            coef = self.coef(p.ranked_activity_names.index(a.name))
            obj.append((coef, self.ideal_plays[p, a]))
            obj.append((EPSILON * coef, self.plays[p, a]))

        self.model.objective = maximize(sum(c * v for (c, v) in obj))
                            

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

    # TODO: duplicate of find_player_by_name, remove one of the two.
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

        self.model += xsum(self.plays[player, a] for a in act) >= 1

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
        self.plays[player, activity].lb = 1

    def set_min_players_activity_by_name(
            self,
            activity_name: str,
            min_number: Optional[int]=None
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
        self.nb_players[act[0]].lb = min_number
        print(f"Minimal number of players set to {min_number}")

    def solve(self, result_name: Option[str]=None, verbose=False) \
    -> MatchResult:
        status = self.model.optimize()
        if status != OptimizationStatus.OPTIMAL:
            print(status)
            raise RuntimeError("Error while solving the problem. Maybe the "
                               "constraints where unsatisfiable?")

        res = MatchResult(self.players, self.activities, result_name)
        for (p, a), v in self.plays.items():
            if v.x >= 0.9:
                res.add(p, a)
        return res

    # TODO: dead code
    def raise_player_nb_activities(self, name: str, nb: int) -> None:
        player = self.find_player_by_name(name)
        assert player.ideal_activities <= nb <= player.max_activities
        self.nb_activities[player].ub = nb
