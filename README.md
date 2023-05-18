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

## Description de l'algorithme

L'algorithme consiste en une succession des *passes*. Une passe consiste, à partir d'une liste de joueureuses, à donner une activité au plus de gens dans cette liste. L'attribution des rôles se fait en deux temps :
1. Dans un premier temps, on exécute des passes, jusqu'à ce que tout le monde ait atteint le nombre *souhaité* d'activité ou ne puisse plus jouer d'autres activités.
2. Ensuite, pour les personnes ayant atteint le nombre souhaité d'activité mais pas le nombre *maximal*, on exécute des passes, jusqu'à ce que tout le monde ait atteint le nombre maximal d'activité ou ne puisse plus jouer d'autres activités.

### Méthode d'affectation pour les passes

Il est possible de paramétrer l'algorithme en changeant la méthode d'affectation des passes. Actuellement, la méthode utilisée est un algorithme hôpital-résident. Chaque joueureuse (jouant le rôle d'un résident) classe les activités selont ses vœux. Pour chaque activité, le classement des joueureuses est le suivant : les joueureuses ayant jusque-là le moins d'activité sont avantagée, puis les joueureuses ayant classé l'activité en question le plus haut. Pour le reste, l'ordre est randomisé.

Pour ce qui est des blacklists, si deux personnes ne peuvent pas jouer ensemble mais sont affectées à la même activité, l'une d'entre elles obtient l'activité. L'autre n'obtient pas d'activité cette passe-là.

### Gestion des conflits
Les conflits sont des contraintes empêchant à un·e joueureuse de jouer une activité. Voici les différents types de conflits pris en compte :
1. Il n'est pas possible de jouer une activité en même temps que l'on joue.
2. Il n'est pas possible de jouer de jouer deux activités en même temps.
3. Contraintes temporelles demandées par les joueureuses (pas deux jeux le même jour, deux jours de suite, etc.)
4. Blacklist : une personne ne veut pas jouer dans la même session qu'une autre.
5. Activité pleine.

Pour le conflit n°1, pour chaque organisateurice, les activités rentrant en conflit avec une organisation sont retirées. Pour le retrait des activité se fait à la fois durant les passes (comme décrit précédemment) entre entre les passes. Pour tous autres conflits, le retrait se fait à la fin de chaque passe.
