# Tutoriel SurePython

Ce tutoriel montre le parcours SurePython actuel de bout en bout.

Objectif :

```text
scanner -> prévisualiser -> appliquer -> tester -> journaliser -> rollback
```

SurePython reste volontairement petit. Il ne sécurise aujourd'hui qu'une micro-modification : ajouter une docstring squelette à une fonction ou méthode Python ciblée, uniquement si elle n'a pas déjà de docstring.

## 1. Préparer l'environnement

Depuis le dépôt :

```powershell
cd C:\dev\datasette-lab\surePython
```

Vérifier Git :

```powershell
git status --short
git branch --show-current
```

Le worktree doit être propre avant une modification réelle.

Créer ou recréer une `.venv` Python 3.12 si nécessaire :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

Puis vérifier :

```powershell
.\.venv\Scripts\python.exe -m surepython --help
New-Item -ItemType Directory -Force .\.tmp
$env:TEMP = "$PWD\.tmp"
$env:TMP = "$PWD\.tmp"
.\.venv\Scripts\python.exe -m pytest --basetemp .\.tmp\pytest_tutorial
```

Si la `.venv` locale est cassée ou pointe vers un interpréteur supprimé, voir [dépannage Windows](WINDOWS_TROUBLESHOOTING.md).

## 2. Scanner le projet

Sortie texte humaine :

```powershell
.\.venv\Scripts\python.exe -m surepython scan tests\fixtures
```

Sortie JSON structurée :

```powershell
.\.venv\Scripts\python.exe -m surepython scan tests\fixtures --format json
```

Sortie CSV :

```powershell
.\.venv\Scripts\python.exe -m surepython scan tests\fixtures --format csv
```

Les champs sont :

- `file`
- `type`
- `name`
- `qualified_name`
- `line_start`
- `line_end`
- `has_docstring`

Le scan sert de carte avant l'opération. Avant la chirurgie, l'imagerie.

## 3. Prévisualiser une modification

Exemple avec une méthode :

```powershell
.\.venv\Scripts\python.exe -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run
```

Le mode `--dry-run` :

- applique les vérifications de sécurité
- cible le même symbole qu'une vraie opération
- construit le code modifié en mémoire
- affiche un diff prévisionnel
- ne modifie pas le fichier
- ne lance pas pytest

Vérifier qu'aucun changement n'a été écrit :

```powershell
.\.venv\Scripts\python.exe -m surepython diff
git status --short
```

## 4. Appliquer sur une copie de travail propre

Pour éviter de salir une fixture versionnée pendant un essai manuel, copier d'abord le fichier dans une zone temporaire versionnée ou dans un dépôt de test séparé. Pour un vrai projet, utiliser directement le fichier cible seulement si le worktree est propre.

Commande réelle avec tests et log SQLite :

```powershell
.\.venv\Scripts\python.exe -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --test --db .\surepython_lab.db
```

Effets attendus :

- une seule docstring squelette est ajoutée
- le diff Git est affiché
- `python -m pytest` est lancé
- le statut pytest est imprimé
- l'opération est enregistrée dans SQLite

Si pytest échoue, SurePython retourne un code d'erreur. La modification reste appliquée ; il n'y a pas de rollback automatique implicite.

## 5. Consulter le diff

```powershell
.\.venv\Scripts\python.exe -m surepython diff
```

Cette commande affiche simplement :

```powershell
git diff --stat
git diff
```

Si aucun dépôt Git n'est détecté, SurePython refuse.

## 6. Journalisation SQLite

`add-docstring --db` écrit automatiquement une ligne dans `surepython_operations`.

La commande manuelle existe toujours :

```powershell
.\.venv\Scripts\python.exe -m surepython log --db .\surepython_lab.db
```

Elle rejoue le dernier état d'opération local vers une base SQLite choisie. Elle ne remplace pas l'auto-log et l'auto-log ne la supprime pas.

La base peut ensuite être inspectée avec SQLite, Datasette ou `sqlite-utils`.

## 7. Prévisualiser un rollback

Le rollback est explicite et exige une base SQLite :

```powershell
.\.venv\Scripts\python.exe -m surepython rollback --last --db .\surepython_lab.db --dry-run
```

SurePython vérifie notamment :

- présence d'un enregistrement `add-docstring` compatible
- fichier actuel présent
- dépôt Git propre
- fichier dans la racine autorisée
- hash actuel égal à `after_sha256`
- restauration reconstructible vers `before_sha256`

Le `--dry-run` du rollback utilise le même chemin de reconstruction byte-exact que le rollback réel.

## 8. Appliquer un rollback

Seulement si le dry-run est correct :

```powershell
.\.venv\Scripts\python.exe -m surepython rollback --last --db .\surepython_lab.db
```

Le rollback réel :

- restaure uniquement l'opération `add-docstring` journalisée
- écrit les octets restaurés seulement après validation du hash
- journalise une opération `rollback` avec statut `rolled_back`

Vérifier ensuite :

```powershell
.\.venv\Scripts\python.exe -m surepython diff
git status --short
```

## 9. Validation recommandée

Avant revue ou tag :

```powershell
New-Item -ItemType Directory -Force .\.tmp
$env:TEMP = "$PWD\.tmp"
$env:TMP = "$PWD\.tmp"
.\.venv\Scripts\python.exe -m pytest --basetemp .\.tmp\pytest_tutorial
.\.venv\Scripts\python.exe -m surepython scan tests\fixtures --format json
.\.venv\Scripts\python.exe -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run
.\.venv\Scripts\python.exe -m surepython diff
git status --short
```

Pour valider un rollback réel, utiliser une opération fraîche dans un dépôt propre ou une copie contrôlée. Ne pas réutiliser une base historique incohérente pour prouver le comportement actuel.

## 10. Ce que le tutoriel prouve

Ce parcours prouve que SurePython sait actuellement :

- cartographier les symboles Python
- prévisualiser une micro-modification
- ajouter une docstring squelette à un symbole précis
- lancer pytest après une vraie modification
- journaliser dans SQLite
- restaurer une opération cohérente sans approximation

Il ne prouve pas que SurePython peut faire n'importe quelle modification Python. Ce n'est pas son rôle actuel.
