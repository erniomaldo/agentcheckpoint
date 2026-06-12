# AgentCheckpoint

**Servidor MCP de almacenamiento atómico clave-valor para coordinación de agentes de IA.**

Evita que tus agentes de IA trabajen con estado obsoleto. AgentCheckpoint es un servidor
MCP (Model Context Protocol) minimalista respaldado por SQLite que brinda a tus agentes
un almacén de estado compartido y atómico — **siempre devolviendo el último valor escrito**.

```bash
pip install agentcheckpoint
```

Luego agrégalo a tu cliente MCP:

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

## El Problema

Los almacenes de memoria semántica (bases vectoriales, agentmemory, etc.) están diseñados
para hechos, no para coordinación de estado. Cuando múltiples agentes leen/escriben
estado compartido:

- `memory.save()` crea **nuevas entradas** en lugar de actualizar — se acumulan decenas
  de versiones obsoletas
- `memory.recall()` devuelve resultados por **similitud semántica**, no por la última
  marca de tiempo
- Los agentes leen estado desactualizado y **vuelven a ejecutar trabajo ya completado**

## La Solución — 100 líneas de Python

AgentCheckpoint es un almacén clave-valor con escrituras atómicas, **diseñado para
coordinación de estado, no para memoria**.

- **Siempre lo último** — `get_state(key)` devuelve el único valor actual
- **Escrituras atómicas** — `force_set_state(key, value)` siempre actualiza, nunca añade
- **Seguro contra conflictos** — `set_state(key, value, expected_version)` detecta
  conflictos de lectura-modificación-escritura
- **Respaldado por SQLite** — cero infraestructura, un solo archivo, modo WAL
- **Una tabla, cinco herramientas** — lo suficientemente simple para entenderlo en 5 minutos

## Herramientas

| Herramienta | Descripción |
|-------------|-------------|
| `get_state` | Lee el valor actual, versión y timestamp de una clave |
| `set_state` | Escribe con guardia de versión opcional (detección OCC de conflictos) |
| `force_set_state` | Escritura atómica incondicional (para flujos de un solo escritor) |
| `list_state` | Lista claves que coinciden con un patrón SQL LIKE |
| `delete_state` | Elimina una clave permanentemente |

## Inicio Rápido

### 1. Instalación

```bash
pip install agentcheckpoint
# o
uv pip install agentcheckpoint
```

### 2. Agregar a tu cliente MCP

Copia y pega la configuración para tu plataforma. Después de agregarla,
**reinicia tu cliente**.

#### 🟣 Claude Desktop

Edita `claude_desktop_config.json`:

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

Agrega a `~/.claude/settings.json` bajo `mcpServers`:

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

O usa la CLI:

```bash
claude mcp add checkpoint -- python -m agentcheckpoint
```

#### 🟢 Cursor

Agrega a `~/.cursor/mcp.json`:

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

Agrega a `~/.codeium/windsurf/mcp_config.json`:

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

Agrega a `~/.continue/config.json` bajo `experimental.mcpServers` (o `mcpServers`
según la versión):

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

Agrega a `~/.hermes/config.yaml` bajo `mcp_servers`:

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Luego ejecuta `/reload-mcp` en sesión, o reinicia el gateway.

#### 🐍 Cualquier cliente con soporte uvx

Si tu cliente soporta `uvx` (la mayoría modernos lo hacen):

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

### 3. Verificar que funciona

Una vez configurado, pregúntale a tu agente:

> "¿Qué herramientas tengo del servidor MCP checkpoint?"

Deberías ver cinco herramientas: `get_state`, `set_state`, `force_set_state`,
`list_state` y `delete_state` (prefijadas con `mcp_checkpoint_` en algunos clientes).

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

## Ejemplo: Coordinación Multi-Agente

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

## Configuración

| Variable de entorno | Por defecto | Descripción |
|---------------------|-------------|-------------|
| `CHECKPOINT_DB_PATH` | `~/.hermes/checkpoints.db` | Ruta de la base de datos SQLite |

## Arquitectura

```
┌──────────────┐     MCP stdio     ┌──────────────────┐     SQLite WAL    ┌──────────┐
│  Agente /    │ ────────────────→ │  agentcheckpoint  │ ───────────────→ │ state.db │
│  Cron Worker │ ←──────────────── │  Servidor MCP     │ ←─────────────── │ (1 file) │
└──────────────┘                   └──────────────────┘                  └──────────┘
```

El servidor se ejecuta como un subproceso stdio. Las herramientas se autodescubren
a través del cliente MCP. Sin puertos de red, sin contenedor, sin configuración más
allá de agregarlo a tu `mcpServers`.

## ¿Por qué no usar agentmemory / base vectorial?

AgentCheckpoint no reemplaza la memoria — es una herramienta diferente para un
trabajo diferente:

| | AgentCheckpoint | Memoria Vectorial/Semántica |
|---|---|---|
| **Propósito** | Coordinación de estado | Hechos, aprendizaje, recuperación |
| **Escritura** | Siempre reemplaza (UPDATE) | Siempre añade (INSERT) |
| **Lectura** | Coincidencia exacta de clave (`SELECT WHERE key=?`) | Similitud semántica (`ORDER BY distance`) |
| **Concurrencia** | Guardia de versión (OCC) | Ninguna |
| **Persistencia** | SQLite WAL (transaccional) | Varía según el backend |

**Úsalos juntos**: AgentCheckpoint para estado compartido (planes, checkpoints,
bloqueos), memoria vectorial para descubrimientos, observaciones y hechos.

## Desarrollo

```bash
git clone https://github.com/erniomaldo/agentcheckpoint
cd agentcheckpoint
pip install -e ".[dev]"
```

## Licencia

MIT

---

## Idiomas

- [English](README.en.md)
- [Português](README.pt.md)
- [Français](README.fr.md)
