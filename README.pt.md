# AgentCheckpoint

**Servidor MCP de armazenamento atômico chave-valor para coordenação de agentes de IA.**

Evita que seus agentes de IA trabalhem com estado obsoleto. AgentCheckpoint é um servidor
MCP (Model Context Protocol) minimalista com suporte a SQLite que oferece a seus agentes
um armazenamento de estado compartilhado e atômico — **sempre retornando o último valor escrito**.

```bash
pip install agentcheckpoint
```

Em seguida, adicione ao seu cliente MCP:

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

## O Problema

Os armazenamentos de memória semântica (bases vetoriais, agentmemory, etc.) são projetados
para fatos, não para coordenação de estado. Quando múltiplos agentes leem/escrevem
estado compartilhado:

- `memory.save()` cria **novas entradas** em vez de atualizar — dezenas de versões
  obsoletas se acumulam
- `memory.recall()` retorna resultados por **similaridade semântica**, não pelo último
  timestamp
- Os agentes leem estado desatualizado e **reexecutam trabalho já concluído**

## A Solução — 100 linhas de Python

AgentCheckpoint é um armazenamento chave-valor com escritas atômicas, **projetado para
coordenação de estado, não para memória**.

- **Sempre o último** — `get_state(key)` retorna o único valor atual
- **Escritas atômicas** — `force_set_state(key, value)` sempre atualiza, nunca adiciona
- **Seguro contra conflitos** — `set_state(key, value, expected_version)` detecta
  conflitos de leitura-modificação-escrita
- **Suportado por SQLite** — zero infraestrutura, um único arquivo, modo WAL
- **Uma tabela, cinco ferramentas** — simples o suficiente para entender em 5 minutos

## Ferramentas

| Ferramenta | Descrição |
|---|---|
| `get_state` | Lê o valor atual, versão e timestamp de uma chave |
| `set_state` | Escreve com guarda de versão opcional (detecção OCC de conflitos) |
| `force_set_state` | Escrita atômica incondicional (para fluxos de um único escritor) |
| `list_state` | Lista chaves que correspondem a um padrão SQL LIKE |
| `delete_state` | Remove uma chave permanentemente |

## Início Rápido

### 1. Instalação

```bash
pip install agentcheckpoint
# o
uv pip install agentcheckpoint
```

### 2. Adicionar ao seu cliente MCP

Copie e cole a configuração para sua plataforma. Após adicioná-la,
**reinicie seu cliente**.

#### 🟣 Claude Desktop

Edite `claude_desktop_config.json`:

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

Adicione em `~/.claude/settings.json` sob `mcpServers`:

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

Ou use a CLI:

```bash
claude mcp add checkpoint -- python -m agentcheckpoint
```

#### 🟢 Cursor

Adicione em `~/.cursor/mcp.json`:

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

Adicione em `~/.codeium/windsurf/mcp_config.json`:

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

Adicione em `~/.continue/config.json` sob `experimental.mcpServers` (ou `mcpServers`
dependendo da versão):

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

Adicione em `~/.hermes/config.yaml` sob `mcp_servers`:

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Em seguida, execute `/reload-mcp` na sessão, ou reinicie o gateway.

#### 🐍 Qualquer cliente com suporte a uvx

Se seu cliente suporta `uvx` (a maioria dos modernos suporta):

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

### 3. Verificar se funciona

Uma vez configurado, pergunte ao seu agente:

> "Quais ferramentas tenho do servidor MCP checkpoint?"

Você deve ver cinco ferramentas: `get_state`, `set_state`, `force_set_state`,
`list_state` e `delete_state` (prefixadas com `mcp_checkpoint_` em alguns clientes).

### 4. Uso básico

```python
# Ejemplo: guardar y leer un checkpoint
mcp_checkpoint_force_set_state(
    key="proyecto:build-status",
    value='{"phase": "testing", "passed": 13, "failed": 2}'
)

# Más tarde...
status = mcp_checkpoint_get_state(key="proyecto:build-status")
# → {value: {...}, version: 1, updated_at: "2026-06-12"}
```

## Exemplo: Coordenação Multi-Agente

```python
# Agente A lee el plan actual
state = client.call_tool("get_state", {"key": "workflow:plan-hoy"})
plan = json.loads(state.value)
# plan.current_index = 5, plan.current_status = "completada"

# Agente A toma la siguiente tarea
plan.current_index += 1  # ahora 6
plan.current_status = "en-progreso"
client.call_tool("force_set_state", {
    "key": "workflow:plan-hoy",
    "value": json.dumps(plan)
})

# ... El Agente A trabaja en la tarea ...

# Agente A la marca como completada
plan.tasks[6].status = "completada"
plan.current_status = "completada"
client.call_tool("force_set_state", {
    "key": "workflow:plan-hoy",
    "value": json.dumps(plan)
})

# Agente B (siguiente tick) lee — siempre obtiene lo último
```

## Configuração

| Variável de ambiente | Padrão | Descrição |
|---|---|---|
| `CHECKPOINT_DB_PATH` | `~/.hermes/checkpoints.db` | Caminho do banco de dados SQLite |

## Arquitetura

```
┌──────────────┐     MCP stdio     ┌──────────────────┐     SQLite WAL    ┌──────────┐
│  Agente /    │ ────────────────→ │  agentcheckpoint  │ ───────────────→ │ state.db │
│  Cron Worker │ ←──────────────── │  Servidor MCP     │ ←─────────────── │ (1 file) │
└──────────────┘                   └──────────────────┘                  └──────────┘
```

O servidor é executado como um subprocesso stdio. As ferramentas são autodescobertas
através do cliente MCP. Sem portas de rede, sem contêiner, sem configuração além
de adicioná-lo ao seu `mcpServers`.

## Por que não usar agentmemory / base vetorial?

AgentCheckpoint não substitui a memória — é uma ferramenta diferente para um
trabalho diferente:

| | AgentCheckpoint | Memória Vetorial/Semântica |
|---|---|---|
| **Propósito** | Coordenação de estado | Fatos, aprendizado, recuperação |
| **Escrita** | Sempre substitui (UPDATE) | Sempre adiciona (INSERT) |
| **Leitura** | Correspondência exata de chave (`SELECT WHERE key=?`) | Similaridade semântica (`ORDER BY distance`) |
| **Concorrência** | Guarda de versão (OCC) | Nenhuma |
| **Persistência** | SQLite WAL (transacional) | Varia conforme o backend |

**Use-os juntos**: AgentCheckpoint para estado compartilhado (planos, checkpoints,
bloqueios), memória vetorial para descobertas, observações e fatos.

## Desenvolvimento

```bash
git clone https://github.com/erniomaldo/agentcheckpoint
cd agentcheckpoint
pip install -e ".[dev]"
```

## Licença

MIT

---

## Idiomas

- [Español](README.md)
- [English](README.en.md)
- [Français](README.fr.md)
