from __future__ import annotations

from typing import List, Dict
import csv

from base import Player, Activity

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
