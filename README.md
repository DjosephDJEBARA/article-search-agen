# Agent de recherche d'articles — recherche automatique toutes les heures

Ce dossier contient un petit agent qui cherche des articles scientifiques
correspondant à des critères précis (composite 3 phases, matrice rigide, 2
populations d'inclusions plus molles, VER 3D, etc.) et te dit lesquels
correspondent vraiment.

## Deux versions, selon ce que tu veux

| | `search_agent_free.py` (par défaut) | `search_agent.py` |
|---|---|---|
| **Coût** | **0 €, gratuit à vie** | ~quelques centimes/mois (API Claude) |
| **Méthode** | Score par mots-clés (règles) | Évaluation intelligente par Claude |
| **Précision** | Bonne, mais peut rater des nuances | Meilleure, comprend le contexte |
| **Workflow à utiliser** | `hourly_search_free.yml` | `hourly_search.yml` |

**Utilise la version gratuite (`_free`) par défaut** — c'est celle
recommandée ci-dessous. Si un jour tu veux passer à la version avec Claude
(plus précise), regarde la section tout en bas.

## Ce que fait la version gratuite, à chaque exécution

1. Interroge l'API **Semantic Scholar** (gratuite, sans clé) avec plusieurs
   requêtes définies dans `search_agent_free.py`.
2. Ignore les articles déjà vus lors des exécutions précédentes (mémorisés
   dans `seen_papers.json`).
3. Attribue un **score** à chaque nouvel article, en comptant les mots-clés
   pertinents présents dans le titre/résumé (+1 par mot-clé positif comme
   "Hashin-Shtrikman", "RVE", "soft inclusion"...), et en soustrayant des
   points si des mots-clés du cas inverse apparaissent (-2 pour "hard
   particle", "stiff filler"...).
4. Ajoute les articles dont le score dépasse un seuil (4 par défaut) dans
   `results.md`, avec les mots-clés trouvés et un extrait du résumé.

## Installation (environ 5 minutes, une seule fois — version gratuite)

### 1. Crée un dépôt GitHub

- Va sur [github.com/new](https://github.com/new)
- Crée un nouveau dépôt (public ou privé, les deux fonctionnent)
- Mets tous les fichiers de ce dossier dedans

### 2. Supprime les fichiers de la version payante (optionnel mais conseillé, pour éviter la confusion)

- Tu peux supprimer `search_agent.py` et
  `.github/workflows/hourly_search.yml` si tu es sûr de vouloir rester
  sur la version gratuite — garde seulement `search_agent_free.py` et
  `.github/workflows/hourly_search_free.yml`

### 3. Active les Actions

- Va dans l'onglet **Actions** de ton dépôt GitHub
- Si demandé, clique pour activer les workflows
- Le script se lancera automatiquement toutes les heures à partir de
  maintenant — **aucune clé API à configurer**

### 4. (Optionnel) Teste-le tout de suite, sans attendre une heure

- Onglet **Actions** → sélectionne **"Hourly Article Search Agent (Free)"**
  → **Run workflow** → **Run workflow** (bouton vert)
- Regarde les logs en temps réel pour voir ce qu'il trouve

## Pour consulter les résultats

Le fichier `results.md`, à la racine du dépôt, s'enrichit à chaque
exécution. Ouvre-le directement sur GitHub (il s'affiche proprement en
Markdown) pour voir tous les articles trouvés, avec l'explication de
Claude pour chacun.

## Pour ajuster les critères de recherche

Ouvre `search_agent_free.py` :

- **`QUERIES`** (en haut du fichier) : les mots-clés de recherche envoyés
  à Semantic Scholar — ajoute, retire, ou modifie des lignes librement
- **`POSITIVE_KEYWORDS`** : les mots qui font monter le score d'un article
  (+1 chacun) — ajoute des termes si tu penses à d'autres mots-clés
  pertinents
- **`NEGATIVE_KEYWORDS`** : les mots qui font baisser le score (-2 chacun)
  — utile pour écarter automatiquement le cas inverse (charge rigide dans
  matrice molle)
- **`SCORE_THRESHOLD`** : le score minimum pour qu'un article soit
  rapporté (4 par défaut) — baisse-le si tu veux voir plus de résultats
  (avec plus de bruit), monte-le pour être plus sélectif

Pas besoin de toucher au fichier `.yml` sauf si tu veux changer la
fréquence (actuellement toutes les heures — `cron: '0 * * * *'`).

## Coût

**0 €, gratuit indéfiniment**, avec la version `_free` :
- Semantic Scholar : gratuit, sans clé
- GitHub Actions : gratuit pour les dépôts publics ; ~2000 minutes/mois
  gratuites pour les dépôts privés (ce script tourne quelques secondes
  par heure, donc largement dans la limite gratuite même en privé)
- Aucune API payante utilisée

## Si tu changes d'avis et veux la version avec Claude (payante, plus précise)

Les fichiers `search_agent.py` et `hourly_search.yml` (sans `_free`) sont
la version qui utilise l'API Claude pour une évaluation plus fine
(comprend le contexte, pas juste des mots-clés). Coût estimé : quelques
centimes par mois pour ce volume de recherche. Vois les instructions dans
l'historique de la conversation si tu veux basculer dessus plus tard.

## Limitation à connaître

Semantic Scholar n'indexe pas forcément un nouvel article **immédiatement**
à sa publication — le délai est généralement de quelques jours. "Toutes les
heures" veut donc dire que tu seras informé rapidement une fois qu'un
article apparaît dans leur base, pas au moment exact de sa publication par
l'éditeur.
