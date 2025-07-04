# MurderWeekMatching

Un programme permettant d'effectuer l'affectation de joueureuses à des activités.

Le programme prend en entrée un planning d'activités, et pour chaque joueureuses, une liste de choix ordonnés et des contraintes.

## Bibliothèques nécessaires

Ce programme nécessite l'utilisation des bibliothèques *pandas* et *Python-MIP*. Vous pouvez les installer à l'aides de la commande :
```
pip install pandas mip
```

Pour tester le projet, il faut installer pytest et lancer la commande suivante :
```
pytest test/tests.py
```

## Contraintes

**Limites d'inscriptions :**
- Les activités peuvent avoir un nombre maximal de participant·es.
- Les joueureuses peuvent avoir un nombre d'activités idéal, et un nombre d'activités maximal.

**Contraintes temporelles :**
- Les joueureuses peuvent demander à ne pas participer à deux activités le même
  jour.
- Les joueureuses peuvent demander à ne pas participer et organiser le même
  jour.
- Les joueureuses peuvent demander à ne pas participer deux jours de suite, trois jours de suite, ou quatre jours et plus de suite.
- Les joueureuses peuvent demander à ne pas participer à deux activités un soir et le lendemain matin.

Également, les joueureuses peuvent demander à ne pas participer à la même activité qu'un·e autre joueureuse. Enfin, l'algorithme s'assure qu'un·e joueureuse ne joue pas ou ne participe pas à deux activités en même temps.

## Comment utiliser ce programme ?

Pour effectuer l'attribution des murders, voici la méthode à utiliser :
1. À partir du formulaire d'inscription, extraire un fichier d'inscription.
2. Effectuer un premier planning et le décrire en un fichier d'activité.
3. Lancer le programme à l'aide de ces deux fichiers pour générer des premières attribution.
4. En analysant la première attribution, effectuer des ajustements au planning, afin de permettre le remplissage des activités incomplètes et que le plus de personnes puissent jouer un nombre satisfaisant d'activités. Il est possible par exemple de déplacer des sessions ou de retirer des activités qui ne pourront pas être remplies.
5. Générer une nouvelle attribution, puis répéter les étapes d'ajustements jusqu'à obtenir une attribution satisfaisante.

Le programme principal est sous la forme d'un notebook jupyter, dans le fichier `main.ipynb`.

## Format des fichiers en entrée

Pour faire tourner le programme, il faut utiliser deux fichiers, au format CSV :
- un fichier d'activité, indiquant pour chaque activités les informations nécessaires (nom, capacité, horaires, organisateurices).
- un fichier d'inscription, indiquant pour chaque joueureuses les informations nécessaires (nom, classement des vœux, disponibilités, contraintes).

Pour comprendre le format, vous pouvez vous aider des fichiers en exemple `data/format_standard_activites.csv` et `data/format_standard_inscriptions.csv`.

## Fichiers de sortie

Le programme extrait deux fichiers CSV en sortie. Le premier fichiers donne pour chaque activité la liste des joueureuses et des organisateurices (avec possibilité d'enlever). Le but est d'avoir un fichier facilement copiable dans un tableur.

Le deuxième fichier donne pour chaque joueureuses la liste des activités où iel est pris·e, refusée·e, indisponible et ou iel organise, ainsi que leurs horaires et rang dans le classement de læ joueureuse. Ce fichier n'a pas vocation à être diffusé. Il sert à avoir une idée des joueureuses qui sont plus ou moins avantagé·e par l'algorithme, pour pouvoir éventuellement rééquilibrer.

Note : ce dernier fichier indique également le nombre d'activité sous la forme "*nombre*/*ideal*, max=*max*". Ainsi, lorsqu'un·e joueureuse a eu plus d'activités que demandé, on peut avoir une indication de la forme "3/2, max=4". Ça peut être perturbant, mais c'est un comportement normal.

## Autres fonctionnalités

La méthode `r0.compare(r1)` permet de comparer deux affectations `r0` et `r1`. Pour chaque activité `a`, les joueureuses qui joue l'activité `a` dans l'affectation `r0` mais pas dans l'affectation `r1` sont indiqué·es avec un symbole `+` et les joueureuses qui jouent dans l'affectation `r1` mais pas dans l'affectation `r0` sont indiqué·es avec un symbole `-`.

**TODO**
- Comparer deux affectations lorsque le planning n'est pas exactement le même.
- Extraire les joueureuses disponibles à un créneau donné.
- Extraire les joueureuses disponibles souhaitant jouer une certaine murder à un créneau donné.

## Description de l'algorithme

Le cœur de l'algorithme est un algorithme de d'optimisation linéaire. Le fait qu'un·e joueureuse $j$ joue une activité $a$ est représenté par une variable linéaire $v_{j, a} \in \{0, 1\}$, le nombre de jeux d'un·e joueureuse $j$ est représenté par une variable $n_j$ et le nombre de joueureuses participant à une activité $a$ est représenté par une variable $n_a$. L'ensemble des contraintes (limites de joueureuses par activité, limites de jeux par joueureuses, contraintes temporelles, blacklists) sont traduites en contraintes linéaires entre les $v_{j, a}$, $n_j$ et $n_a$. Nous essayons de maximiser la somme des valeur des jeux joués, avec comme valeur l'inverse du rang du jeu dans le classement de læ joueureuses (1 pour un vœu n°1, $$\frac{1}{2}$$ pour un jeu n°2, $$\frac{1}{3}$$ pour un jeu n°3, etc.). À noter que le nombre de jeu idéal est pris en compte. Si un·e joueureuse demande idéalement trois jeux, les jeux au-delà du troisième seront comptés avec une valeur plus faible.

Il est possible d'ajouter des contraintes supplémentaires, afin par exemple :
- De s'assure qu'un·e joueureuse joue un jeu donné.
- D'assurer un remplissage minimal à une activité donnée.

Attention cependant, donner trop de contraintes du genre peut rendre le problème insolvable, ou empêcher des joueureuses de jouer des activités qu'iels désirent. Si toutes les activités ne sont pas remplies, il peut être préférable de changer le planning plutôt que de forcer des affectations.
