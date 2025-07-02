from typing import List
from pathlib import Path
import pandas
import random

import sys
sys.path.append("src")
from base import print_dispos
from matcher import Matcher
from loader import set_year, load_activities_and_players

# À modifiez pour mettre l'année courante.
set_year("2024")
# À modifier : mettre les fichiers utilisés pour 
# Par exemple :
# activities, players = load_activities_and_players(
#         Path('data/activite.csv'),
#         Path('data/inscription_a_la_murder_week_2024.csv'),
#         verbose=True)
activities, players = load_activities_and_players(
        Path('data/activite-2.csv'),
        Path('data/inscription_a_la_murder_week_2024.csv'),
        verbose=True)

# Pour concevoir le planning, il peut être utile de savoir quels sont les
# créneaux où plusieurs personnes sont disponibles pour un jeu:
print_dispos(players, "César et le Village des Irréductibles", True)

matcher = Matcher(players, activities)
print("")
# On affecte de force des joueureuses à des activités.
# Le principal exemple d'utilisation est le suivant : lorsqu'un jeu est
# organisé dans un appartement, on force l'affectation des colocs au jeu.
matcher.force_assign_activity("Joseph Lenormand", "Épilogue")
matcher.force_assign_activity("Pauline Boutrelle", "Trouble-fête")

res = matcher.solve(verbose=True)

# Affichage en terminal des résultats:
res.print_players_status()
res.print_activities_status()
# Export des résultat dans des fichiers CSV plus lisibles:
#res.export_activities_to_csv("out/output-activites.csv")
#res.export_players_to_csv("out/output-players.csv")

### Comparaison entre deux solutions différentes.
##from matcher import exponential_coef
##matcher = Matcher(players, activities, exponential_coef(0.5))
##other = matcher.solve()
##res.compare(other)

