# BMAD Patches

Ce dossier contient les fichiers patches appliques par `install.py` apres
`npx bmad-method install --full`.

La structure miroir celle de `_bmad/` :

```
_bmad-patches/
  bmm/
    workflows/
      4-implementation/
        dev-story/
          instructions.xml   <- Step 10 : generation HANDOFF.md
        code-review/
          instructions.xml   <- Step 7 : git commit + HANDOFF.md
  _config/
    agents/
      bmm-dev.customize.yaml <- Lecture HANDOFF.md au demarrage
```

## Patches inclus

### dev-story Step 10 — HANDOFF.md
A la fin de chaque story implementee, genere `HANDOFF.md` a la racine du
projet avec : story en cours, prochaine commande a lancer, decisions cles.

### code-review Step 7 — Git commit + HANDOFF.md
Apres un code review :
- Si done : `git commit -m "feat: Story X.Y -- titre"`
- Si in-progress : commit de review + HANDOFF.md avec issues a corriger

### bmm-dev.customize.yaml — Session handoff
L'agent dev lit `HANDOFF.md` au debut de chaque session pour reprendre
le contexte sans recharger tout le projet.

## Mise a jour

Quand BMAD met a jour ses workflows, re-appliquer les patches :
```bash
python install.py "Nom" --no-kanban
```
Ou manuellement :
```bash
cp _bmad-patches/bmm/workflows/4-implementation/dev-story/instructions.xml \
   _bmad/bmm/workflows/4-implementation/dev-story/instructions.xml
```
