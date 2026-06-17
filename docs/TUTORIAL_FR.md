# Tutoriel SurePython

Ce tutoriel montre le parcours SurePython actuel de bout en bout.

Objectif :

```text
capabilities -> scanner -> prévisualiser -> appliquer -> tester -> journaliser -> rollback
```

SurePython reste volontairement petit. Il sécurise aujourd'hui dix micro-modifications :

- ajouter une docstring squelette à une fonction ou méthode Python ciblée, uniquement si elle n'a pas déjà de docstring ;
- retirer une docstring explicite d'un module, d'une classe, d'une fonction ou d'une méthode ciblée, uniquement si le texte attendu correspond exactement ;
- ajouter une annotation de retour explicite à une fonction ou méthode Python ciblée, uniquement si elle n'a pas déjà d'annotation de retour.
- retirer une annotation de retour explicite à une fonction ou méthode Python ciblée, uniquement si l'annotation correspond exactement à celle attendue ;
- ajouter une annotation de paramètre explicite à une fonction ou méthode Python ciblée, uniquement si le paramètre n'a pas déjà d'annotation.
- retirer une annotation de paramètre explicite à une fonction ou méthode Python ciblée, uniquement si l'annotation attendue correspond exactement à l'annotation présente.
- ajouter une instruction `import` explicite au niveau module, avec un seul binding, uniquement si ce binding n'existe pas déjà.
- retirer une instruction `import` explicite au niveau module, uniquement si l'instruction attendue correspond exactement à l'instruction présente.
- ajouter un décorateur explicite à une fonction, méthode ou classe ciblée, uniquement si ce décorateur n'est pas déjà présent et si la cible n'est pas ambiguë.
- retirer un décorateur explicite d'une fonction, méthode ou classe ciblée, uniquement si l'expression attendue et la position attendue correspondent exactement.

SurePython ne devine jamais le type. Codex ou l'humain propose l'annotation ; SurePython la vérifie et l'insère exactement.

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

Avant de demander une opération à SurePython, Codex doit pouvoir interroger les capacités réelles :

```powershell
.\.venv\Scripts\python.exe -m surepython capabilities --format json
```

Cette sortie est le contrat machine-readable. Elle évite à Codex de deviner les opérations disponibles.

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
.\.venv\Scripts\python.exe -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run --format json
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
.\.venv\Scripts\python.exe -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --test --db .\surepython_lab.db --format json
```

Effets attendus :

- une seule docstring squelette est ajoutée
- le diff Git est affiché
- `python -m pytest` est lancé
- le statut pytest est imprimé
- l'opération est enregistrée dans SQLite

Si pytest échoue, SurePython retourne un code d'erreur. La modification reste appliquée ; il n'y a pas de rollback automatique implicite.

## 4 bis. Retirer une docstring explicite

Prévisualisation :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-docstring tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-docstring "Build a service." --dry-run
.\.venv\Scripts\python.exe -m surepython remove-docstring tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-docstring "Build a service." --dry-run --format json
```

Application réelle avec tests et log :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-docstring tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-docstring "Build a service." --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython remove-docstring tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-docstring "Build a service." --test --db .\surepython_lab.db --format json
```

Contrat :

- le texte attendu de la docstring est fourni explicitement ;
- le module, la classe, la fonction ou la méthode ciblée doit avoir une docstring exacte correspondante ;
- une docstring absente, déplacée ou différente est refusée ;
- les suites inline ne sont pas supportées ;
- le corps de la fonction ou de la classe n'est pas modifié autrement ;
- le rollback reste explicite et vérifié par hash exact.

## 4 ter. Ajouter une annotation de retour explicite

Prévisualisation :

```powershell
.\.venv\Scripts\python.exe -m surepython add-return-type src\service.py --function UserService.load_user --annotation "User | None" --dry-run
.\.venv\Scripts\python.exe -m surepython add-return-type src\service.py --function UserService.load_user --annotation "User | None" --dry-run --format json
```

Application réelle avec tests et log :

```powershell
.\.venv\Scripts\python.exe -m surepython add-return-type src\service.py --function UserService.load_user --annotation "User | None" --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython add-return-type src\service.py --function UserService.load_user --annotation "User | None" --test --db .\surepython_lab.db --format json
```

Contrat :

- l'annotation est fournie explicitement ;
- l'annotation doit être syntaxiquement valide ;
- une annotation existante est refusée ;
- aucun import n'est ajouté automatiquement ;
- le corps de la fonction n'est pas modifié ;
- le rollback reste explicite et vérifié par hash.

SurePython valide la syntaxe de l'annotation, pas sa disponibilité sémantique dans le projet. Si l'annotation référence un nom non importé ou non défini au runtime, `--test` doit révéler l'échec.

## 4 ter. Retirer une annotation de retour explicite

Prévisualisation :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-return-type src\service.py --function UserService.load_user --expect-annotation "User | None" --dry-run
.\.venv\Scripts\python.exe -m surepython remove-return-type src\service.py --function UserService.load_user --expect-annotation "User | None" --dry-run --format json
```

Application réelle avec tests et log :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-return-type src\service.py --function UserService.load_user --expect-annotation "User | None" --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython remove-return-type src\service.py --function UserService.load_user --expect-annotation "User | None" --test --db .\surepython_lab.db --format json
```

Contrat :

- l'annotation attendue est fournie explicitement ;
- la comparaison entre l'annotation attendue et l'annotation réelle se fait avant suppression ;
- un retour absent est refusé ;
- un décalage entre l'annotation attendue et l'annotation réelle est refusé ;
- aucun import n'est ajouté automatiquement ;
- le corps de la fonction n'est pas modifié ;
- le rollback reste explicite et vérifié par hash.

SurePython compare les annotations de retour par forme syntaxique, pas par résolution de nom. Les différences de pure mise en forme sont ignorées, mais pas les différences structurelles.

## 4 quater. Ajouter une annotation de paramètre explicite

Prévisualisation :

```powershell
.\.venv\Scripts\python.exe -m surepython add-parameter-type src\service.py --function UserService.load_user --parameter source --annotation "str" --dry-run
.\.venv\Scripts\python.exe -m surepython add-parameter-type src\service.py --function UserService.load_user --parameter source --annotation "str" --dry-run --format json
```

Application réelle avec tests et log :

```powershell
.\.venv\Scripts\python.exe -m surepython add-parameter-type src\service.py --function UserService.load_user --parameter source --annotation "str" --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython add-parameter-type src\service.py --function UserService.load_user --parameter source --annotation "str" --test --db .\surepython_lab.db --format json
```

Contrat :

- le paramètre est fourni explicitement ;
- l'annotation doit être syntaxiquement valide ;
- une annotation existante est refusée ;
- les paramètres variadiques `*args` et `**kwargs` sont refusés ;
- aucun import n'est ajouté automatiquement ;
- le corps de la fonction n'est pas modifié ;
- le rollback reste explicite et vérifié par hash.

Comme pour les retours de fonction, SurePython valide la syntaxe de l'annotation, pas sa disponibilité sémantique dans le projet. Si l'annotation référence un nom non importé ou non défini au runtime, `--test` doit révéler l'échec.

### Retirer une annotation de paramètre explicite

Prévisualisation :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-parameter-type src\service.py --function UserService.load_user --parameter source --expect-annotation "str" --dry-run
.\.venv\Scripts\python.exe -m surepython remove-parameter-type src\service.py --function UserService.load_user --parameter source --expect-annotation "str" --dry-run --format json
```

Application réelle avec tests et log :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-parameter-type src\service.py --function UserService.load_user --parameter source --expect-annotation "str" --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython remove-parameter-type src\service.py --function UserService.load_user --parameter source --expect-annotation "str" --test --db .\surepython_lab.db --format json
```

Contrat :

- l'annotation attendue est fournie explicitement ;
- la suppression ne s'applique que si l'annotation réelle correspond exactement ;
- un paramètre absent est refusé ;
- un paramètre déjà sans annotation est refusé ;
- les paramètres variadiques `*args` et `**kwargs` sont refusés ;
- aucun import n'est ajouté automatiquement ;
- le corps de la fonction n'est pas modifié ;
- le rollback reste explicite et vérifié par hash.

SurePython compare les annotations de paramètre par forme syntaxique. Les différences de pure mise en forme sont ignorées, mais pas les différences structurelles.

## 4 quinquies. Ajouter un import explicite

Prévisualisation :

```powershell
.\.venv\Scripts\python.exe -m surepython add-import tests\fixtures\sample_module.py --statement "import json" --dry-run
.\.venv\Scripts\python.exe -m surepython add-import tests\fixtures\sample_module.py --statement "from pathlib import Path" --dry-run --format json
```

Application réelle avec tests et log :

```powershell
.\.venv\Scripts\python.exe -m surepython add-import tests\fixtures\sample_module.py --statement "from pathlib import Path" --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython add-import tests\fixtures\sample_module.py --statement "from pathlib import Path" --test --db .\surepython_lab.db --format json
```

Contrat :

- l'instruction `import` est fournie explicitement ;
- exactement un binding est autorisé ;
- les imports multiples, relatifs et wildcard sont refusés ;
- les conflits de binding sont refusés ;
- aucun import n'est ajouté automatiquement ;
- le corps du module n'est pas réorganisé globalement ;
- le rollback reste explicite et vérifié par hash.

SurePython valide la syntaxe de l'instruction, pas le sens métier du module. L'agent doit fournir l'import exact à insérer.

## 4 sexies. Retirer un import explicite

Prévisualisation :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-import tests\fixtures\sample_module.py --expect-statement "import json" --dry-run
.\.venv\Scripts\python.exe -m surepython remove-import tests\fixtures\sample_module.py --expect-statement "from pathlib import Path" --dry-run --format json
```

Application réelle avec tests et log :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-import tests\fixtures\sample_module.py --expect-statement "from pathlib import Path" --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython remove-import tests\fixtures\sample_module.py --expect-statement "from pathlib import Path" --test --db .\surepython_lab.db --format json
```

Contrat :

- l'instruction attendue est fournie explicitement ;
- exactement un import top-level est retiré ;
- les imports imbriqués, relatifs, wildcard et multi-binding sont refusés ;
- les ambiguïtés de structure sont refusées ;
- aucun import n'est retiré automatiquement ;
- le corps du module n'est pas réorganisé globalement ;
- le rollback reste explicite et vérifié par hash.

Les commandes `add-docstring`, `remove-docstring`, `add-return-type`, `remove-return-type`, `add-parameter-type`, `remove-parameter-type`, `add-import`, `remove-import`, `add-decorator`, `remove-decorator` et `rollback` peuvent aussi retourner un JSON stable avec `--format json`. Dans ce mode, les opérations réelles exposent un `operation_id` SQLite, alors que les dry-runs renvoient `operation_id: null`.

## 4 septies. Ajouter un décorateur explicite

Prévisualisation :

```powershell
.\.venv\Scripts\python.exe -m surepython add-decorator tests\fixtures\sample_module.py --symbol SampleClass.sample_method --decorator "staticmethod" --position outermost --dry-run
.\.venv\Scripts\python.exe -m surepython add-decorator tests\fixtures\sample_module.py --symbol SampleClass.sample_method --decorator "staticmethod" --position outermost --dry-run --format json
```

Application réelle avec tests et log :

```powershell
.\.venv\Scripts\python.exe -m surepython add-decorator tests\fixtures\sample_module.py --symbol SampleClass.sample_method --decorator "staticmethod" --position outermost --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython add-decorator tests\fixtures\sample_module.py --symbol SampleClass.sample_method --decorator "staticmethod" --position outermost --test --db .\surepython_lab.db --format json
```

Contrat :

- la cible peut être une fonction, une méthode, une fonction asynchrone, une méthode asynchrone ou une classe ;
- le décorateur est fourni explicitement ;
- les positions supportées sont `outermost` et `innermost` ;
- les doublons sont refusés ;
- les conflits de décorateurs de binding comme `staticmethod`, `classmethod` ou `property` sont refusés ;
- aucun décorateur n'est deviné automatiquement ;
- le rollback reste explicite et vérifié par hash.

## 4 octies. Retirer un décorateur explicite

La suppression compare l'expression attendue et sa position avant d'enlever un seul décorateur :

```powershell
.\.venv\Scripts\python.exe -m surepython remove-decorator tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-decorator "classmethod" --expect-position outermost --dry-run
.\.venv\Scripts\python.exe -m surepython remove-decorator tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-decorator "classmethod" --expect-position outermost --dry-run --format json
.\.venv\Scripts\python.exe -m surepython remove-decorator tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-decorator "classmethod" --expect-position outermost --test --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython remove-decorator tests\fixtures\sample_module.py --symbol SampleClass.sample_method --expect-decorator "classmethod" --expect-position outermost --test --db .\surepython_lab.db --format json
```

Contrat :

- l'expression attendue est fournie explicitement ;
- la position attendue est fournie explicitement ;
- `outermost` et `innermost` sont les seules positions supportées ;
- un décorateur absent est refusé ;
- un décalage de position est refusé ;
- un seul décorateur est retiré ;
- le reste de la liste est préservé dans le même ordre ;
- le rollback reste explicite et vérifié par hash.

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

Les opérations réelles avec `--db` écrivent automatiquement une ligne dans `surepython_operations`. Les dry-runs gardent `operation_id: null` dans le JSON et ne créent pas de ligne SQLite.

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
.\.venv\Scripts\python.exe -m surepython rollback --last --db .\surepython_lab.db --dry-run --format json
.\.venv\Scripts\python.exe -m surepython rollback --id 42 --db .\surepython_lab.db --dry-run
.\.venv\Scripts\python.exe -m surepython rollback --id 42 --db .\surepython_lab.db --dry-run --format json
```

SurePython vérifie notamment :

- présence d'un enregistrement compatible (`add-docstring`, `add-return-type` ou `remove-return-type`)
- présence d'un enregistrement compatible (`add-docstring`, `add-return-type`, `remove-return-type`, `add-parameter-type`, ou `add-import`)
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
.\.venv\Scripts\python.exe -m surepython rollback --last --db .\surepython_lab.db --format json
.\.venv\Scripts\python.exe -m surepython rollback --id 42 --db .\surepython_lab.db
.\.venv\Scripts\python.exe -m surepython rollback --id 42 --db .\surepython_lab.db --format json
```

Le rollback réel :

- restaure uniquement l'opération compatible journalisée (`add-docstring`, `add-return-type`, `add-parameter-type`, ou `add-import`)
- restaure uniquement l'opération compatible journalisée (`add-docstring`, `add-return-type`, `remove-return-type`, `add-parameter-type`, ou `add-import`)
- écrit les octets restaurés seulement après validation du hash
- journalise une opération `rollback` avec statut `rolled_back`
- le sélecteur explicite `--id` ne peut être utilisé qu'à la place de `--last`

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
.\.venv\Scripts\python.exe -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method --dry-run --format json
.\.venv\Scripts\python.exe -m surepython add-return-type tests\fixtures\sample_module.py --function SampleClass.sample_method --annotation "str" --dry-run --format json
.\.venv\Scripts\python.exe -m surepython add-parameter-type tests\fixtures\sample_module.py --function SampleClass.sample_method --parameter source --annotation "str" --dry-run --format json
.\.venv\Scripts\python.exe -m surepython diff
git status --short
```

Pour valider un rollback réel, utiliser une opération fraîche dans un dépôt propre ou une copie contrôlée. Ne pas réutiliser une base historique incohérente pour prouver le comportement actuel.

## 10. Ce que le tutoriel prouve

Ce parcours prouve que SurePython sait actuellement :

- cartographier les symboles Python
- prévisualiser une micro-modification
- ajouter une docstring squelette à un symbole précis
- ajouter une annotation de retour explicite à un symbole précis
- ajouter une annotation de paramètre explicite à un symbole précis
- ajouter une instruction `import` explicite au niveau module
- lancer pytest après une vraie modification
- journaliser dans SQLite
- restaurer une opération cohérente sans approximation

Il ne prouve pas que SurePython peut faire n'importe quelle modification Python. Ce n'est pas son rôle actuel.

## 11. Phase 3.1: recovery hardening

À partir de la phase 3.1, les opérations transactionnelles sont aussi protégées par un verrou projet et par des manifestes plus stricts.

En pratique:

- `plan preview`, `plan apply`, `plan rollback` et `plan recover` refusent `PROJECT_MUTATION_LOCKED` si un autre processus détient le verrou
- les manifestes transactionnels sont écrits atomiquement et vérifiés par checksum
- une récupération incohérente refuse avec `PLAN_MANIFEST_INVALID`, `PLAN_STATE_INVALID` ou `PLAN_RECOVERY_CONFLICT` selon le défaut
- des points d'injection de panne ne servent qu'aux smokes et aux tests de récupération

Le tutoriel reste valable, mais les smokes de la phase 3.1 servent à prouver le durcissement d'exécution, pas à élargir le périmètre fonctionnel.
