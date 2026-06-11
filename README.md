# SurePython v0.1

SurePython est un CLI local de micro-modification Python contrôlée.

Périmètre v0.1:

- `scan`
- `add-docstring`
- `diff`
- `log`

Règles principales:

- un seul fichier par opération
- un seul symbole par opération
- refus si le dépôt git n'est pas propre
- refus si la cible est hors racine projet
- refus si une docstring existe déjà
- affichage du diff après modification
- journalisation SQLite compatible Datasette

Exemples:

```powershell
python -m surepython scan .
python -m surepython add-docstring tests\fixtures\sample_module.py --function sample_function --test
python -m surepython add-docstring tests\fixtures\sample_module.py --function SampleClass.sample_method
python -m surepython diff
python -m surepython log --db .\didier_lab.db
```

Implementation note:

- The local `.vendor3` tree and `sitecustomize.py` bootstrap remain in place as an environment fix for ACL issues in this workspace.
- They are documented as bootstrap infrastructure, not behavioral shims.
