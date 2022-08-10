from random import shuffle
from typing import List, Dict, Optional, Tuple, Iterator, Set

from activityMatch import Activity, Player, Matching

from matching.games import HospitalResident

class HospitalResidentMatching(Matching):
    """Instantiate a hospital-resident procedure for the matching.
    
    TODO: describe the algorithm."""

    def cast_if_one_wish(self, players: List[Player], verbose=False) -> List[Tuple[Player, Activity]]:
        """For each player that has no activity yet and only one possible remaining wish,
        try to give it to them.
        """
        assignation = []
        for p in players:
            if not p.is_last_chance():
                continue
            activity = p.wishes[0]
            assignation.append((p, activity))

        return assignation

    def prepare_hospital_resident_dictionaries(self) -> Tuple[Dict, Dict, Dict]:
        player_wishes: Dict[Player, List[Activity]] = {p: p.possible_wishes()
                                                       for p in self.active_players}

        capacities = {a: a.remaining_slots() for a in self.active_activities}

        activities_waiting_list: Dict[Activity, List[Player]] = {
            a: self.generate_activity_waiting_list(player_wishes, a)
            for a in self.active_activities}

        # removing activities that no one wished
        unwanted = [a for (a, w) in activities_waiting_list.items() if len(w) == 0]
        for a in unwanted:
            activities_waiting_list.pop(a)
            capacities.pop(a)

        # removing players with no wishes
        finished = [p for (p, w) in player_wishes.items() if w == []]
        for p in finished:
            player_wishes.pop(p)
            for (a, wl) in activities_waiting_list.items():
                if p in wl:
                    wl.remove(p)

        return player_wishes, activities_waiting_list, capacities


    def generate_activity_waiting_list(self, player_wishes: Dict[Player, List[Activity]],
                                       activity: Activity) -> List[Player]:
        # Get the players that wanted this activity
        interested_players: List[Player] = [p for (p, wishes) in player_wishes.items() if activity in wishes]
        # Shuffle them
        shuffle(interested_players)
        # Then, sort by the number of activities that a given player already has and then
        # the rank of the activity on the wishlist of each player, so that a wish
        # in first position is stronger than a wish in 10th position, but a player with 2 activities has priority over
        # someone with 5
        interested_players.sort(key=lambda p: (len(p.activities), p.activity_rank(activity)))
        return interested_players

    def cast_with_hospital_residents(self, verbose=False) -> List[Tuple[Player, Activity]]:
        player_wishes, activities_waiting_list, capacities = self.prepare_hospital_resident_dictionaries()

        game = HospitalResident.create_from_dictionaries(player_wishes, activities_waiting_list, capacities)
        match = game.solve(optimal="resident")

        # Match returns a Dict[Hospital, List[Resident]]
        # So to access the Activity and Player underneath, we must use the .name method
        # The objects are cloned, so we have to find the activity back with its ID
        assignation = []
        for (a, cast) in match.items():
            for p in cast:
                activity = self.find_activity(a.name.id)
                player = self.find_player(p.name.id)
                assignation.append((player, activity))
        return assignation
    
    def assignation_pass(self, players: List[Player], verbose=False) -> List[Tuple[Player, Activity]]:
        print("Casting in priority the players with only one wish and no casts yet")
        cast_if_one_wish = self.cast_if_one_wish(players)
        if cast_if_one_wish:
            print(f"Detected {len(cast_if_one_wish)} players with one wish and no cast yet")
            shuffle(cast_if_one_wish)
            return cast_if_one_wish

        print("No more priority players. Now casting like usual")
        assignation = self.cast_with_hospital_residents(verbose=verbose)
        shuffle(assignation)
        return assignation