# AgentCheckpoint

**Serveur MCP de stockage atomique clé-valeur pour la coordination d'agents d'IA.**

Empêche tes agents d'IA de travailler avec un état obsolète. AgentCheckpoint est un serveur
MCP (Model Context Protocol) minimaliste soutenu par SQLite qui offre à tes agents
un magasin d'état partagé et atomique — **retournant toujours la dernière valeur écrite**.

```bash
pip install agentcheckpoint
```

Puis ajoute-le à ton client MCP :

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

## Le Problème

Les magasins de mémoire sémantique (bases vectorielles, agentmemory, etc.) sont conçus
pour des faits, pas pour la coordination d'état. Lorsque plusieurs agents lisent/écrivent
un état partagé :

- `memory.save()` crée **de nouvelles entrées** au lieu de mettre à jour — des dizaines
  de versions obsolètes s'accumulent
- `memory.recall()` retourne des résultats par **similarité sémantique**, pas par la dernière
  estampille temporelle
- Les agents lisent un état obsolète et **réexécutent un travail déjà terminé**

## La Solution — 100 lignes de Python

AgentCheckpoint est un magasin clé-valeur avec écritures atomiques, **conçu pour
la coordination d'état, pas pour la mémoire**.

- **Toujours le dernier** — `get_state(key)` retourne l'unique valeur actuelle
- **Écritures atomiques** — `force_set_state(key, value)` met toujours à jour, n'ajoute jamais
- **Sûr contre les conflits** — `set_state(key, value, expected_version)` détecte
  les conflits de lecture-modification-écriture
- **Soutenu par SQLite** — zéro infrastructure, un seul fichier, mode WAL
- **Une table, cinq outils** — assez simple pour le comprendre en 5 minutes

## Outils

| Outil | Description |
|-------|-------------|
| `get_state` | Lit la valeur actuelle, la version et l'horodatage d'une clé |
| `set_state` | Écrit avec garde de version optionnelle (détection OCC des conflits) |
| `force_set_state` | Écriture atomique inconditionnelle (pour flux à un seul écrivain) |
| `list_state` | Liste les clés correspondant à un motif SQL LIKE |
| `delete_state` | Supprime une clé définitivement |

## Démarrage Rapide

### 1. Installation

```bash
pip install agentcheckpoint
# ou
uv pip install agentcheckpoint
```

### 2. Ajouter à ton client MCP

Copie et colle la configuration pour ta plateforme. Après l'avoir ajoutée,
**redémarre ton client**.

#### 🟣 Claude Desktop

Modifie `claude_desktop_config.json` :

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

Ajoute à `~/.claude/settings.json` sous `mcpServers` :

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

Ou utilise la CLI :

```bash
claude mcp add checkpoint -- python -m agentcheckpoint
```

#### 🟢 Cursor

Ajoute à `~/.cursor/mcp.json` :

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

Ajoute à `~/.codeium/windsurf/mcp_config.json` :

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

Ajoute à `~/.continue/config.json` sous `experimental.mcpServers` (ou `mcpServers`
selon la version) :

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

Ajoute à `~/.hermes/config.yaml` sous `mcp_servers` :

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Exécute ensuite `/reload-mcp` en session, ou redémarre la passerelle.

#### 🐍 N'importe quel client avec support uvx

Si ton client supporte `uvx` (la plupart des clients modernes le font) :

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

### 3. Vérifier que ça fonctionne

Une fois configuré, demande à ton agent :

> « Quels outils ai-je du serveur MCP checkpoint ? »

Tu devrais voir cinq outils : `get_state`, `set_state`, `force_set_state`,
`list_state` et `delete_state` (préfixés par `mcp_checkpoint_` sur certains clients).

### 4. Utilisation de base

```python
# Exemple : sauvegarder et lire un checkpoint
mcp_checkpoint_force_set_state(
    key="projet:build-status",
    value='{"phase": "testing", "passed": 13, "failed": 2}'
)

# Plus tard...
status = mcp_checkpoint_get_state(key="projet:build-status")
# → {value: {...}, version: 1, updated_at: "2026-06-12"}
```

## Exemple : Coordination Multi-Agent

```python
# Agent A lit le plan actuel
state = client.call_tool("get_state", {"key": "workflow:plan-aujourdhui"})
plan = json.loads(state.value)
# plan.current_index = 5, plan.current_status = "terminée"

# Agent A prend la tâche suivante
plan.current_index += 1  # maintenant 6
plan.current_status = "en-cours"
client.call_tool("force_set_state", {
    "key": "workflow:plan-aujourdhui",
    "value": json.dumps(plan)
})

# ... L'Agent A travaille sur la tâche ...

# Agent A la marque comme terminée
plan.tasks[6].status = "terminée"
plan.current_status = "terminée"
client.call_tool("force_set_state", {
    "key": "workflow:plan-aujourdhui",
    "value": json.dumps(plan)
})

# Agent B (prochain tick) lit — obtient toujours la dernière version
```

## Configuration

| Variable d'environnement | Par défaut | Description |
|--------------------------|------------|-------------|
| `CHECKPOINT_DB_PATH` | `~/.hermes/checkpoints.db` | Chemin de la base de données SQLite |

## Architecture

```
┌──────────────┐     MCP stdio     ┌──────────────────┐     SQLite WAL    ┌──────────┐
│  Agent /     │ ────────────────→ │  agentcheckpoint  │ ───────────────→ │ state.db │
│  Cron Worker │ ←──────────────── │  Serveur MCP      │ ←─────────────── │ (1 file) │
└──────────────┘                   └──────────────────┘                  └──────────┘
```

Le serveur s'exécute comme un sous-processus stdio. Les outils sont auto-découverts
via le client MCP. Pas de ports réseau, pas de conteneur, pas de configuration
au-delà de l'ajouter à ton `mcpServers`.

## Pourquoi ne pas utiliser agentmemory / base vectorielle ?

AgentCheckpoint ne remplace pas la mémoire — c'est un outil différent pour un
travail différent :

| | AgentCheckpoint | Mémoire Vectorielle/Sémantique |
|---|---|---|
| **But** | Coordination d'état | Faits, apprentissage, récupération |
| **Écriture** | Remplace toujours (UPDATE) | Ajoute toujours (INSERT) |
| **Lecture** | Correspondance exacte de clé (`SELECT WHERE key=?`) | Similarité sémantique (`ORDER BY distance`) |
| **Concurrence** | Garde de version (OCC) | Aucune |
| **Persistance** | SQLite WAL (transactionnel) | Varie selon le backend |

**Utilise-les ensemble** : AgentCheckpoint pour l'état partagé (plans, checkpoints,
verrous), la mémoire vectorielle pour les découvertes, observations et faits.

## Développement

```bash
git clone https://github.com/erniomaldo/agentcheckpoint
cd agentcheckpoint
pip install -e ".[dev]"
```

## Licence

MIT

---

## Langues

- [Español](README.md)
- [English](README.en.md)
- [Português](README.pt.md)
