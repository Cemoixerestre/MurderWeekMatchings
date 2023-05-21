# MurderWeekMatching

Un programme pour effectuer l'attribution des murders à la murder week.

## Comment utiliser ce programme ?

Pour effectuer l'attribution des murders, voici la méthode à utiliser :
1. À partir du formulaire d'inscription, extraire un fichier de joueureuses.
2. Effectuer un plannnig, extraire un fichier d'activité.
3. Lancer le programme à l'aide de ses deux fichiers pour générer des premières attribution.
4. En analysant la première attribution, effectuer des ajustements au planning, afin de permettre le remplissage des activités incomplètes et que le plus de personnes puissent jouer un nombre satisfaisant d'activités. Il est possible par exemple de déplacer des sessions ou de retirer des activités qui ne pourront pas être remplies.
5. Générer une nouvelle attribution, puis répéter les étapes d'ajustements jusqu'à obtenir une attribution satisfaisante.

Le programme principal est sous la forme d'un notebook jupyter, dans le fichier `main.ipynb`.

## Format des fichiers en entrée

Pour faire tourner le programme, il faut utiliser deux fichiers, au format CSV :
- un fichier d'activité, indiquant pour chaque activités les informations nécessaires (nom, capacité, horaires, organisateurices).
- un fichier de joueureuses, indiquant pour chaque joueureuses les informations nécessaires (nom, classement des vœux, disponibilités, contraintes).
Des exemples de fichiers sont trouvables dans le dossiers `data/`.

## Bibliothèques nécessaires ##

Ce programme nécessite l'utilisation des bibliothèques *pandas* et *Python-MIP*. Vous pouvez les installer à l'aides de la commande :
```
pip install pandas mip
```

## Description de l'algorithme

Le cœur de l'algorithme est un algorithme de d'optimisation linéaire. Le fait qu'un·e joueureuse $j$ joue une activité $a$ est représenté par une variable linéaire $v_{j, a} \in \{0, 1\}$, le nombre de jeux d'un·e joueureuse $j$ est représenté par une variable $n_j$ et le nombre de joueureuses participant à une activité $a$ est représenté par une variable $n_a$. L'ensemble des contraintes (limites de joueureuses par activité, limites de jeux par joueureuses, contraintes temporelles, blacklists) sont traduites en contraintes linéaires entre les $v_{j, a}$, $n_j$ et $n_a$. La fonction que nous essayons de maximiser est :
$$\sum_{j, a} d^{r(j, a)} v_{j, a}$$
Avec $d \in [0, 1]$ un paramètre et $r(j, a)$ le rang de l'activité $a$ dans le classement de læ joueureuse $j$.

Afin de tenir compte du nombre idéal d'activités donnés par certain·es joueureuses, qui peut-être inférieur au nombre, la recherche d'une solution se fait en deux temps :
1. Dans un premier temps, les nombres d'activités $n_j$ sont bornés par les nombres idéaux d'activité par joueureuses $i_j$. On fait tourner l'algorithme une première fois pour trouver une solution.
2. On « fige dans le marbre » la solution trouvée. Si une variable $v_{j, a}$ est égale à 1, ce qui signifie que læ joueureuse $j$ joue l'activité $a$, on remonte la borne inférieure de la variable $v_{j, a}$ à 1 afin que la deuxième passe d'optimisation affecte toujours l'activité $a$ à $j$.
3. On relâche les contraintes sur le nombre d'activité par joueureuses, en réhaussant la borne supérieures des $n_j$ par les nombre maximaux d'activités $m_j$.
4. On effectue une deuxième passe d'optimisation pour affecter les dernières places restantes aux joueureuses qui ont leur nombre idéal d'activités mais qui peuvent en jouer plus.

Il est possible d'ajouter des contraintes supplémentaires, afin par exemple :
- De s'assure qu'un·e joueureuse joue un jeu donné.
- D'assurer un remplissage minimal à une activité donnée.

Attention cependant, donner trop de contraintes du genre peut rendre le problème insolvable, ou empêcher des joueureuses de jouer des activités qu'iels désirent. Si toutes les activités ne sont pas remplies, il peut être préférable de changer le planning plutôt que de forcer des affectations.

Le paramètre $d$ change la nature de la solution. De manière empirique, à l'aide des données d'inscription de la murder week 2022, j'ai pu observer que :
- Si $d \leq 0.2$, beaucoup de jeux ne sont pas remplis.
- Si $d \in [0.3, 0.5]$, tous les jeux sont remplis et tout le monde obtient son activité demandée en premier.
- Si $d \in [0.6, 0.7]$, tous les jeux sont remplis et toutes les personnes sauf une obtiennent leur activité favorite. Plus personne obtiennent le nombre de jeu idéal que pour $d \in [0.3, 0.5]$.
- Si $d \geq 0.8$, un certain nombre de personnes n'obtiennent pas leur activité demandée en premier.
La meilleur solution trouvée a été pour $d = 0.6$ ou $0.7$, en forçant l'affectation à son jeu préféré pour la personne en question.
