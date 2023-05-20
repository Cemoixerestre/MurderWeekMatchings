from typing import List
from pathlib import Path
import pandas
import random

from activityMatch import Matching
from loader import load_activities_and_players

random.seed(20)
activities, players = load_activities_and_players(Path('data/planning_3.csv'),
                                                  Path('data/dispos_3.csv'))

matching = Matching(players, activities)
print("")

matching.force_assign_activity('Aurélie Montibert',
                               "Les Enfants de la Nuit d'Eté")
matching.solve(verbose=True)
matching.print_players_status()
matching.print_activities_status()
