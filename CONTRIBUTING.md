# Contribuer à CodeNavigator

Merci de votre intérêt pour CodeNavigator. Ce document décrit la façon de contribuer au projet dans un cadre open source, avec un niveau d'exigence adapté à une utilisation par les équipes de Talan.

## Objectif

CodeNavigator est un outil d'exploration de code, de génération de documentation et de RAG. Les contributions sont les bienvenues tant qu'elles restent cohérentes avec l'architecture existante, la lisibilité du code et la maintenabilité du projet.

## Table des matières

- [Avant de commencer](#avant-de-commencer)
- [Nommage et conventions de travail](#nommage-et-conventions-de-travail)
  - [Branches](#branches)
  - [Issues](#issues)
  - [Commits](#commits)
- [Vérifications avant de proposer une contribution](#vérifications-avant-de-proposer-une-contribution)
- [Conventions de code](#conventions-de-code)
- [Tests](#tests)

## Avant de commencer

1. Lisez le [README](README.md) pour comprendre les fonctionnalités, les prérequis et les commandes principales.
2. Vérifiez qu'aucune issue ou discussion existante ne couvre déjà le sujet.
3. Travaillez sur une branche dédiée créée à partir de `dev`.

## Nommage et conventions de travail

Pour garder un historique lisible et faciliter les revues, merci de suivre ces conventions.

### Branches

- Préférez des noms explicites et courts, par exemple `feat/add-docs-export`, `fix/chat-reset`, `docs/contributing-update`.
- Évitez les noms vagues comme `patch`, `update` ou `test`.
- Si possible, rattachez le nom de la branche au sujet de l'issue.
- Créez toujours votre branche à partir de `dev` en suivant la convention de nommage `<type>/<short-description>#<issueID>` (par exemple `feat/add-login#7`, `docs/update-readme#15`). Cela s'aligne avec Conventional Commits et améliore la cohérence du projet.

```bash
git checkout dev
git pull origin dev
git checkout -b feat/my-feature dev
```

### Issues

- Décrivez le besoin métier ou technique en une phrase claire.
- Ajoutez le contexte, l'objectif attendu et, si utile, les étapes de reproduction.
- Indiquez les critères d'acceptation quand le sujet n'est pas purement technique.
- Donnez un titre court, orienté action, qui permet de comprendre le sujet en un coup d'œil.

### Commits

Ce dépôt suit la convention de commits de type Conventional Commits.

Format recommandé :

```text
<type>(<scope>): <short description>
```

Types courants : `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`, `perf`, `ci`.

Exemples :

- `feat(graph): add module dependency export`
- `fix(chat): handle empty conversation history`
- `docs(contributing): add contribution rules`

Gardez les messages courts, précis et cohérents avec le contenu réel du commit.

## Vérifications avant de proposer une contribution

Avant d'ouvrir une pull request, exécutez au minimum les vérifications pertinentes pour votre changement.

### Tests Python

Dans cet espace de travail, la commande de référence est :

```powershell
CodeNavigator-Explore-understand-and-document-code/.venv/Scripts/python.exe -m pytest -q
```

### Frontend

Si votre changement touche l'interface ou les composants React, lancez les tests et la vérification TypeScript du frontend selon les scripts définis dans `frontend/package.json`.

### Qualité

- Vérifiez que le code reste cohérent avec le style du projet.
- Gardez les changements ciblés et limités au besoin fonctionnel.
- Ajoutez ou mettez à jour les tests quand le comportement change.

## Conventions de code

### Python

- Utilisez `snake_case` pour les fonctions et variables.
- Utilisez `PascalCase` pour les classes et modèles Pydantic.
- Ajoutez des annotations de type sur les signatures publiques.
- Préférez `logging` à `print()`.
- Gardez les routes FastAPI explicites avec `response_model` et `status_code`.
- Ne retournez pas de dictionnaires bruts si un modèle existe.

### React / TypeScript

- Utilisez des composants fonctionnels.
- Préférez les exports nommés sauf pour les pages.
- Évitez `any` sans justification claire.
- Suivez la structure existante du dossier `frontend/src`.

## Tests

Le projet suit une logique de tests proche du module modifié.

- Backend Python : `pytest`
- API FastAPI : tests d'intégration avec `httpx` et `AsyncClient`
- Frontend : `@testing-library/react`

Quand vous ajoutez une fonctionnalité, visez au moins un cas nominal et un cas d'erreur quand cela a du sens.

## Flux de contribution

1. Ouvrez une issue ou décrivez clairement le besoin avant de coder si le changement est important.
2. Implémentez la modification sur une branche dédiée.
3. Ajoutez ou mettez à jour les tests.
4. Vérifiez le résultat localement.
5. Ouvrez une pull request avec une description claire du problème, de la solution et des validations réalisées.

## Bonnes pratiques pour les pull requests

- Une PR doit idéalement couvrir un seul sujet.
- Décrivez le contexte métier si le changement touche l'exploration de code, la génération ou le RAG.
- Indiquez les commandes de test exécutées.
- Joignez des captures ou extraits de sortie si l'UI ou les docs changent.

## Sécurité et secrets

Ne commitez jamais de secrets, clés API ou données sensibles. Si une contribution nécessite une nouvelle configuration, documentez-la dans le README ou dans les fichiers de configuration appropriés.

## Questions et support

Si vous contribuez au nom d'une équipe Talan, mentionnez le contexte d'usage dans la pull request afin de faciliter la revue et la priorisation.

Pour une question, précisez si possible :

- le contexte fonctionnel ou métier,
- le fichier ou le module concerné,
- ce qui a déjà été tenté,
- la sortie d'erreur ou le comportement observé,
- si la question concerne l'architecture, le packaging, les tests ou le déploiement.

Plus la question est précise, plus il est facile de vous répondre rapidement et utilement.
