# AgentCheckpoint

**Magasin atomique de paires clé-valeur pour la coordination d'agents IA.**

[![PyPI - Version](https://img.shields.io/pypi/v/agentcheckpoint?style=flat-square&logo=pypi&color=blue)](https://pypi.org/project/agentcheckpoint/)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/agentcheckpoint?style=flat-square&logo=python&color=yellow)](https://pypi.org/project/agentcheckpoint/)
[![License](https://img.shields.io/pypi/l/agentcheckpoint?style=flat-square&color=green)](https://github.com/erniomaldo/agentcheckpoint/blob/main/LICENSE)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/agentcheckpoint?style=flat-square&color=purple)](https://pypistats.org/packages/agentcheckpoint)
[![GitHub Repo Stars](https://img.shields.io/github/stars/erniomaldo/agentcheckpoint?style=flat-square)](https://github.com/erniomaldo/agentcheckpoint)

---

<p align="center">
  <strong>Un serveur MCP qui empêche vos agents de travailler sur un état obsolète.</strong><br>
  <em>~150 lignes de Python, propulsé par SQLite WAL, zéro infrastructure.</em>
</p>

---

🌐 [🇺🇸 English](README.md) · [🇪🇸 Español](README.es.md) · [🇧🇷 Português](README.pt.md)

---

## 📦 Installation

```bash
pip install agentcheckpoint
```

Ajoutez-le ensuite à votre client MCP préféré (voir [Configuration Client](#-configuration-client)).

---

## 🤨 Le Problème

Les mémoires sémantiques — bases vectorielles, agentmemory, mem0, etc. — sont conçues pour les **faits et l'apprentissage**, pas pour la **coordination d'état**. Lorsque plusieurs agents lisent et écrivent un état partagé, voici ce qui se passe :

| Problème | Ce qui se produit | Conséquence |
|----------|------------------|-------------|
| `memory.save()` n'a pas de mise à jour | Chaque sauvegarde crée une **nouvelle entrée** | Des dizaines de versions obsolètes s'accumulent |
| `memory.recall()` utilise la similarité | Retourne des résultats **sémantiquement proches**, pas les plus récents | Les agents lisent un état périmé |
| Pas de contrôle de concurrence | Deux agents lisent le même état, écrivent sans coordination | Les modifications s'écrasent mutuellement, perte de données |
| Pas de garde de version | Un écrasement peut en aveugler un autre | **Workflows corrompus, tâches réexécutées** |

**En résumé :** vos agents travaillent avec un état obsolète, réexécutent des tâches déjà terminées, et brûlent des ressources sur des efforts dupliqués.

---

## ✅ La Solution

AgentCheckpoint n'est **pas** un magasin de mémoire — c'est un **magasin d'état partagé avec garanties atomiques**. Considérez-le comme un feu tricolore ou une mémoire partagée pour les agents IA.

```
┌──────────────────────┐    MCP stdio    ┌────────────────────┐    SQLite WAL    ┌──────────────┐
│  Agent A              │ ───────────────→│                    │ ──────────────→│              │
│  Agent B              │ ───────────────→│  AgentCheckpoint   │ ──────────────→│  state.db    │
│  Travailleur Cron C   │ ───────────────→│  Serveur MCP       │ ──────────────→│  (1 fichier) │
│  Pipeline D           │ ←──────────────│                    │ ←──────────────│              │
└──────────────────────┘                  └────────────────────┘                └──────────────┘
```

### Comparaison

| Fonctionnalité | AgentCheckpoint | agentmemory / base vectorielle | Redis | Fichier JSON |
|---------------|----------------|-------------------------------|-------|-------------|
| **Objectif** | Coordination d'état | Faits, apprentissage | Cache générique | Persistance basique |
| **Écriture** | Remplace toujours (UPSERT) | Ajoute toujours (INSERT) | Écrase (sans versionnage) | Écrase tout le fichier |
| **Lecture** | `SELECT WHERE key=?` correspondance exacte | `ORDER BY distance` sémantique | Recherche directe par clé | Analyse et recherche |
| **Concurrence** | Contrôle de concurrence optimiste (OCC) | Aucun | Aucun nativement | Aucune |
| **Persistance** | SQLite WAL (transactionnel, ACID) | Variable selon le backend | RAM / RDB / AOF | Dépend du système de fichiers |
| **Infrastructure** | Zéro — un seul processus stdio | Serveur, API, index | Serveur dédié | Zéro |
| **Outillage MCP** | Natif — auto-découverte des outils | Non | Non | Non |
| **Lignes de code** | ~150 | Des milliers | ~50K+ | ~5 (aucune garantie) |

**Utilisez les deux ensemble :** AgentCheckpoint pour l'état partagé, la mémoire vectorielle / agentmemory pour les faits, observations et découvertes.

---

## 🛠️ Outils (API MCP)

| Outil | Description | Quand l'utiliser |
|-------|-------------|------------------|
| `get_state(clé)` | Lit la valeur actuelle, la version et l'horodatage d'une clé | Avant toute modification |
| `set_state(clé, valeur, version_attendue?)` | Écrit avec garde de version optionnelle (OCC) | Quand **plusieurs** agents écrivent la même clé |
| `force_set_state(clé, valeur)` | Écriture atomique inconditionnelle | Quand un **seul** agent/travailleur possède la clé |
| `list_state(patron?)` | Liste les clés correspondant à un patron SQL LIKE | Audit, découverte, débogage |
| `delete_state(clé)` | Supprime définitivement une clé | Nettoyage d'un état terminé |

Chaque outil est automatiquement découvert via le protocole MCP — aucune configuration supplémentaire nécessaire.

> **Note pour les clients MCP :** chez certains clients, les outils sont préfixés comme `mcp_checkpoint_get_state`, `mcp_checkpoint_set_state`, etc.

---

## 🚀 Démarrage Rapide

### 1. Installation

```bash
pip install agentcheckpoint
# ou avec uv :
uv pip install agentcheckpoint
```

### 2. Ajouter à votre client MCP

La configuration varie selon la plateforme. Après l'ajout, **redémarrez votre client** ou rechargez les serveurs MCP.

#### 🟣 Claude Desktop

Modifiez `claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

#### 🔵 Claude Code

Ajoutez à `~/.claude/settings.json` :

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

Ou via CLI :

```bash
claude mcp add checkpoint -- python -m agentcheckpoint
```

#### 🟢 Cursor

Ajoutez à `~/.cursor/mcp.json` :

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

#### 🟠 Windsurf

Ajoutez à `~/.codeium/windsurf/mcp_config.json` :

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "agentcheckpoint",
      "timeout": 10
    }
  }
}
```

#### ⚪ Continue.dev

Ajoutez à `~/.continue/config.json` :

```json
{
  "experimental": {
    "mcpServers": {
      "checkpoint": {
        "command": "agentcheckpoint",
        "timeout": 10
      }
    }
  }
}
```

#### 🔶 Hermes Agent

Ajoutez à `~/.hermes/config.yaml` :

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Puis exécutez `/reload-mcp` dans la session, ou redémarrez la passerelle.

#### 🐍 Tout client avec support uvx

```json
{
  "mcpServers": {
    "checkpoint": {
      "command": "uvx",
      "args": ["agentcheckpoint"],
      "timeout": 10
    }
  }
}
```

### 3. Vérification

Demandez à votre agent :

> _« Quels outils ai-je depuis le serveur MCP checkpoint ? »_

Vous devriez voir les 5 outils listés ci-dessus.

### 4. Premier point de contrôle

```python
# Sauvegarder l'état
mcp_checkpoint_force_set_state(
    key="project:build-status",
    value='{"phase": "testing", "passed": 13, "failed": 2}'
)

# Lire l'état plus tard
status = mcp_checkpoint_get_state(key="project:build-status")
# → {status: "ok", key: "...", value: {...}, version: 1, updated_at: "2026-06-16T..."}
```

---

## 🎯 Patrons d'Utilisation

### Patron 1 : Écrivain unique (tâches cron, agents solo)

Utilisez `force_set_state` — toujours réussi, toujours remplacé :

```python
# Travailleur nocturne : enregistrer la progression
mcp_checkpoint_force_set_state(
    key="checkpoint:nocturnal-2026-06-16",
    value='{"status": "in-progress", "started_at": "2026-06-16T03:00:00Z"}'
)

# ... traitement ...

mcp_checkpoint_force_set_state(
    key="checkpoint:nocturnal-2026-06-16",
    value='{"status": "completed", "records_processed": 1427, "finished_at": "..."}'
)
```

### Patron 2 : Agents multiples avec OCC (le plus important)

Utilisez `get_state` + `set_state` avec la garde de version (contrôle de concurrence optimiste) :

```python
# 1. LIRE avec version
current = mcp_checkpoint_get_state(key="workflow:plan-today")
plan = json.loads(current["value"])
# plan.current_index = 5, version = 3

# 2. MODIFIER
plan.current_index += 1
plan.current_task = "analysis"

# 3. ÉCRIRE avec la version lue
result = mcp_checkpoint_set_state(
    key="workflow:plan-today",
    value=json.dumps(plan),
    expected_version=current["version"]  # ← garde OCC
)

if result["status"] == "conflict":
    # Un autre agent a modifié l'état → relire et réessayer
    pass
elif result["status"] == "ok":
    # Écriture réussie, nouvelle version assignée
    print(f"Point de contrôle mis à jour, version {result['version']}")
```

Chaque écriture porte la version observée au moment de la lecture. Si un autre agent a modifié la clé entre-temps, l'écriture échoue avec `conflict` — vous relisez et réessayez. C'est le **contrôle de concurrence optimiste (OCC)** standard, le même patron utilisé par Elasticsearch, CouchDB et Git.

### Patron 3 : Verrou distribué

```python
# Tentative d'acquisition d'un verrou (création seule)
result = mcp_checkpoint_set_state(
    key="lock:db-migration",
    value=json.dumps({"owner": "agent-A", "acquired_at": "..."}),
    expected_version=0  # ← ne fonctionne que si la clé N'EXISTE PAS
)

if result["status"] == "ok":
    # Verrou acquis — exécuter l'opération critique
    run_migration()
    # Libération
    mcp_checkpoint_delete_state(key="lock:db-migration")
else:
    # Verrou détenu par un autre — attendre ou abandonner
    pass
```

### Patron 4 : Sauter si fait (garde d'idempotence)

```python
# Avant de commencer : cela a-t-il déjà été fait ?
state = mcp_checkpoint_get_state(key="checkpoint:generate-invoices")
if state["status"] != "not_found":
    print("Travail déjà effectué, passage ignoré")
    return

# Réclamer + exécuter
mcp_checkpoint_force_set_state(
    key="checkpoint:generate-invoices",
    value='{"status": "started"}'
)
# ... faire le travail ...
```

---

## 📐 Convention de Nommage des Clés

Gardez vos clés organisées avec cette structure :

```
<domaine>:<identifiant>[:<attribut>]
```

| Exemple | Objectif |
|---------|----------|
| `workflow:daily-digest` | État d'un workflow multi-étapes |
| `project:agentcheckpoint:build-status` | État de build d'un projet |
| `lock:database-migration` | Mutex pour opération critique |
| `plan:2026-06-16` | Plan d'exécution quotidien |
| `checkpoint:nocturnal-pillar-1` | Point de contrôle du travailleur nocturne |
| `cron:news-morning` | Coordination de tâche cron |

**Bonnes pratiques :**
- Utilisez les deux-points (`:`) comme séparateurs — lisibles et compatibles avec `SELECT LIKE`
- Gardez les clés sous **200 caractères**
- Les valeurs **doivent toujours être du JSON valide**
- Utilisez `list_state(pattern="project:%")` pour trouver toutes les clés d'un domaine

---

## 📊 Référence API

### `get_state(clé)`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `key` | `string` | ✅ | Clé à lire |

**Réponse en cas de succès :**
```json
{"status": "ok", "key": "workflow:plan", "value": "...", "version": 3, "updated_at": "2026-06-16T..."}
```

**Clé introuvable :**
```json
{"status": "not_found", "key": "workflow:plan"}
```

### `set_state(clé, valeur, version_attendue?)`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `key` | `string` | ✅ | Clé à écrire |
| `value` | `string` | ✅ | Valeur (chaîne JSON) |
| `expected_version` | `integer` | ❌ | -1=inconditionnel (défaut), 0=création seule, N=mise à jour versionnée |

**Comportement de la garde de version :**
| `expected_version` | Résultat |
|--------------------|----------|
| `-1` (omis) | Écrit toujours (comme `force_set_state`) |
| `0` | Crée seulement si la clé N'EXISTE PAS. Échoue avec `conflict` si elle existe |
| `N > 0` | Met à jour seulement si la version stockée correspond à N. Échoue avec `conflict` si elle ne correspond pas |

### `force_set_state(clé, valeur)`

Inconditionnel. Écrit toujours. Pas de garde de version.

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `key` | `string` | ✅ | Clé à écrire |
| `value` | `string` | ✅ | Valeur (chaîne JSON) |

### `list_state(patron?)`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `pattern` | `string` | ❌ | Patron SQL LIKE (`%` = texte quelconque, `_` = un caractère). Défaut : `%` |

### `delete_state(clé)`

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `key` | `string` | ✅ | Clé à supprimer |

---

## ⚙️ Configuration

| Variable d'env. | Défaut | Description |
|-----------------|--------|-------------|
| `CHECKPOINT_DB_PATH` | `~/.hermes/checkpoints.db` | Chemin du fichier de base SQLite |

Exemple de chemin personnalisé :

```bash
CHECKPOINT_DB_PATH=/tmp/my-state.db agentcheckpoint
```

---

## 🏗️ Architecture

```
┌──────────────────────┐       stdio (stdin/stdout)      ┌────────────────────┐
│                       │                                  │                    │
│  Client MCP           │ ────── JSON-RPC (MCP) ───────→  │  agentcheckpoint   │
│  (Claude, Cursor,     │ ←────────────────────────────── │  Serveur MCP       │
│   Windsurf, Hermes)   │                                  │                    │
│                       │                                  │  ┌──────────────┐  │
└──────────────────────┘                                  │  │  SQLite WAL   │  │
                                                          │  │  state.db     │  │
                                                          │  │  (1 fichier)  │  │
                                                          │  └──────────────┘  │
                                                          └────────────────────┘
```

### Détails techniques

- **Transport :** stdio (sous-processus MCP) — aucun port réseau, aucun conteneur
- **Base de données :** SQLite en mode WAL (Write-Ahead Logging) pour des lectures concurrentes sans blocage
- **Concurrence :** `PRAGMA synchronous=NORMAL` — équilibre entre durabilité et rapidité
- **Validation :** toutes les valeurs sont validées comme JSON à l'écriture
- **Versionnage :** chaque UPSERT incrémente atomiquement le compteur de version
- **Délai d'attente de connexion :** 5 secondes dans SQLite, 10 secondes recommandé dans le client MCP
- **Atomicité :** les écritures sont transactionnelles — soit totalement persistées, soit pas du tout

---

## ❓ FAQ

**Q : Est-ce qu'AgentCheckpoint remplace agentmemory ?**
R : Non. Ils sont complémentaires. AgentCheckpoint coordonne l'état (qui a fait quoi ? à quelle étape sommes-nous ?). agentmemory stocke les faits et apprentissages (qu'avons-nous découvert ? comment fonctionne X ?). **Utilisez les deux ensemble.**

**Q : Puis-je exécuter plusieurs instances pointant vers le même fichier ?**
R : SQLite WAL supporte plusieurs lecteurs concurrents, mais pour plusieurs écrivains, il est préférable d'utiliser une seule instance du serveur MCP. Pour la haute disponibilité, envisagez de placer le fichier `.db` sur un volume partagé.

**Q : Que se passe-t-il si le processus plante en plein milieu d'une écriture ?**
R : SQLite WAL garantit l'atomicité — soit la totalité du changement est persistée, soit rien ne l'est. Aucune écriture partielle.

**Q : Quelle peut être la taille d'une valeur ?**
R : Les valeurs sont des chaînes JSON. SQLite peut théoriquement gérer jusqu'à ~1 Go, mais nous recommandons de garder les valeurs sous **100 Ko**. Pour les données volumineuses, stockez une référence (chemin de fichier, URL) comme valeur.

**Q : Comment nettoyer les anciens points de contrôle ?**
R : Utilisez `delete_state` pour des clés individuelles, ou écrivez un script qui itère avec `list_state` et supprime en fonction de `updated_at`.

**Q : Est-ce que le TTL / l'auto-expiration est supporté ?**
R : Pas nativement, mais vous pouvez l'implémenter dans votre agent : lors de la lecture, vérifiez `updated_at` et décidez si l'état est obsolète.

---

## 🧑‍💻 Développement

```bash
git clone https://github.com/erniomaldo/agentcheckpoint
cd agentcheckpoint
pip install -e ".[dev]"
```

Le code source se trouve dans `src/agentcheckpoint/` :

| Fichier | Rôle |
|---------|------|
| `__init__.py` | Version du paquet |
| `__main__.py` | Point d'entrée (`python -m agentcheckpoint`) |
| `server.py` | Serveur MCP complet (~150 lignes) |

### Contribution

1. Forkez le dépôt
2. Créez une branche (`git checkout -b feature/awesome-thing`)
3. Faites vos modifications
4. Commitez avec des messages clairs
5. Poussez et ouvrez une Pull Request

---

## 📜 Licence

MIT © [Ernesto Maldonado](https://github.com/erniomaldo)

---

## 🌐 Langues

| Langue | Fichier |
|--------|---------|
| 🇺🇸 English | [`README.md`](README.md) |
| 🇪🇸 Español | [`README.es.md`](README.es.md) |
| 🇫🇷 Français | `README.fr.md` (ce fichier) |
| 🇧🇷 Português | [`README.pt.md`](README.pt.md) |

---

<p align="center">
  <sub>Fait avec ❤️ pour empêcher les agents de marcher sur l'état des autres.</sub><br>
  <sub>Utile ? Laisse une ⭐ sur <a href="https://github.com/erniomaldo/agentcheckpoint">GitHub</a></sub>
</p>
