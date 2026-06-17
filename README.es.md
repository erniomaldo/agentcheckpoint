# AgentCheckpoint

**Almacén atómico clave-valor para coordinación de estado entre agentes de IA.**

[![PyPI - Version](https://img.shields.io/pypi/v/agentcheckpoint?style=flat-square&logo=pypi&color=blue)](https://pypi.org/project/agentcheckpoint/)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/agentcheckpoint?style=flat-square&logo=python&color=yellow)](https://pypi.org/project/agentcheckpoint/)
[![License](https://img.shields.io/pypi/l/agentcheckpoint?style=flat-square&color=green)](https://github.com/erniomaldo/agentcheckpoint/blob/main/LICENSE)

---

<p align="center">
  <strong>Servidor MCP que evita que tus agentes trabajen con estado obsoleto.</strong><br>
  <em>~150 líneas de Python, respaldado por SQLite WAL, sin infraestructura.</em>
</p>

---

🌐 [🇺🇸 English](README.md) · [🇫🇷 Français](README.fr.md) · [🇧🇷 Português](README.pt.md)

---

## 📦 Instalación

```bash
pip install agentcheckpoint
```

Luego agrégalo a tu cliente MCP favorito (salta a [Configuración por Cliente](#-configuración-por-cliente)).

---

## 🤨 El Problema

Los almacenes de memoria semántica —bases vectoriales, `agentmemory`, `mem0`, etc.— están diseñados para **hechos y aprendizaje**, no para **coordinación de estado**. Cuando múltiples agentes leen y escriben estado compartido, te encuentras con esto:

| Problema | Lo que pasa | Consecuencia |
|----------|-------------|--------------|
| `memory.save()` sin update | Cada save crea **una entrada nueva** | Decenas de versiones obsoletas acumuladas |
| `memory.recall()` por similitud | Devuelve lo **semánticamente cercano**, no lo último | Lees estado desactualizado |
| Sin control de concurrencia | Dos agentes leen lo mismo, escriben sin coordinarse | Se pisan los cambios, pérdida de datos |
| Sin guardia de versión | Una escritura puede sobrescribir ciegamente el trabajo de otro agente | **Workflows corruptos, trabajo rehecho** |

**El resultado:** tus agentes trabajan con estado vencido, vuelven a ejecutar tareas ya completadas, y pierdes horas de cómputo en trabajo duplicado.

---

## ✅ La Solución

AgentCheckpoint no es un almacén de memoria — es un **almacén de estado compartido con garantías atómicas**. Piensa en él como un semáforo o una `shared memory` para agentes de IA.

```
┌──────────────────────┐    MCP stdio    ┌────────────────────┐    SQLite WAL    ┌──────────────┐
│  Agente A             │ ───────────────→│                    │ ──────────────→│              │
│  Agente B             │ ───────────────→│  AgentCheckpoint   │ ──────────────→│  state.db    │
│  Cron Worker C        │ ───────────────→│  Servidor MCP      │ ──────────────→│  (1 archivo) │
│  Pipeline D            │ ←──────────────│                    │ ←──────────────│              │
└──────────────────────┘                  └────────────────────┘                └──────────────┘
```

### ¿Qué lo hace diferente?

| Característica | AgentCheckpoint | agentmemory / vector DB | Redis | Archivo JSON |
|---------------|----------------|------------------------|-------|--------------|
| **Propósito** | Coordinación de estado | Hechos, aprendizaje | Caché genérica | Persistencia básica |
| **Escritura** | Siempre reemplaza (UPSERT) | Siempre añade (INSERT) | Sobrescribe (sin versionado) | Sobrescribe todo el archivo |
| **Lectura** | `SELECT WHERE key=?` exacto | `ORDER BY distance` semántico | Key lookup directo | Parsear y buscar |
| **Concurrencia** | Optimistic Concurrency Control (OCC) | Ninguna | Ninguna nativa | Ninguna |
| **Persistencia** | SQLite WAL (transaccional, ACID) | Varía por backend | En RAM / RDB / AOF | Depende del FS |
| **Infraestructura** | Cero — un proceso stdio | Servidor, API, índices | Servidor dedicado | Cero |
| **Tooling MCP** | Nativo — autodescubrimiento de tools | No | No | No |
| **Líneas de código** | ~150 | Miles | ~50K+ | ~5 (sin garantías) |

**Úsalos juntos:** AgentCheckpoint para el estado compartido, y memoria vectorial o agentmemory para hechos, observaciones y descubrimientos.

---

## 🛠️ Herramientas (API MCP)

| Herramienta | Descripción | Cuándo usarla |
|-------------|-------------|---------------|
| `get_state(key)` | Lee el valor actual, versión y timestamp de una clave | Antes de toda modificación |
| `set_state(key, value, expected_version?)` | Escribe con guardia de versión opcional (OCC) | Cuando **múltiples** agentes escriben la misma clave |
| `force_set_state(key, value)` | Escritura atómica incondicional | Cuando **un solo** agente/worker escribe la clave |
| `list_state(pattern?)` | Lista claves por patrón SQL LIKE | Para auditoría, descubrimiento, debugging |
| `delete_state(key)` | Elimina una clave permanentemente | Limpieza de estado completado |

Cada herramienta se autodescubre a través del protocolo MCP — no necesitas configurar nada extra.

> **Nota para clientes MCP:** en algunos clientes las herramientas se prefijan como `mcp_checkpoint_get_state`, `mcp_checkpoint_set_state`, etc.

---

## 🚀 Inicio Rápido

### 1. Instalar

```bash
pip install agentcheckpoint
# o si usas uv:
uv pip install agentcheckpoint
```

### 2. Agregar a tu cliente MCP

La configuración varía según tu plataforma. Después de agregarla, **reinicia tu cliente** o recarga los MCP servers.

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

Agrega a `~/.claude/settings.json`:

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

O desde la CLI:

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

Agrega a `~/.continue/config.json`:

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

Agrega a `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Luego ejecuta `/reload-mcp` en sesión, o reinicia el gateway.

#### 🐍 Cualquier cliente con soporte uvx

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

### 3. Verificar

Pregúntale a tu agente:

> _¿Qué herramientas tengo del servidor MCP checkpoint?_

Deberías ver las 5 herramientas listadas arriba.

### 4. Primer checkpoint

```python
# Guardar estado
mcp_checkpoint_force_set_state(
    key="proyecto:build-status",
    value='{"phase": "testing", "passed": 13, "failed": 2}'
)

# Leer estado después
status = mcp_checkpoint_get_state(key="proyecto:build-status")
# → {status: "ok", key: "...", value: {...}, version: 1, updated_at: "2026-06-16T..."}
```

---

## 🎯 Patrones de Uso

### Patrón 1: Escritor Único (cron jobs, agentes solitarios)

Usa `force_set_state` — siempre funciona, siempre reemplaza:

```python
# Worker nocturno: checkpoint de progreso
mcp_checkpoint_force_set_state(
    key="checkpoint:nocturno-2026-06-16",
    value='{"status": "in-progress", "started_at": "2026-06-16T03:00:00Z"}'
)

# ... procesando ...

mcp_checkpoint_force_set_state(
    key="checkpoint:nocturno-2026-06-16",
    value='{"status": "completed", "records_processed": 1427, "finished_at": "..."}'
)
```

### Patrón 2: Múltiples Agentes con OCC (el más importante)

Usa `get_state` + `set_state` con el version guard (Optimistic Concurrency Control):

```python
# 1. LEER con versión
current = mcp_checkpoint_get_state(key="workflow:plan-hoy")
plan = json.loads(current["value"])
# plan.current_index = 5, version = 3

# 2. MODIFICAR
plan.current_index += 1
plan.current_task = "analisis"

# 3. ESCRIBIR con la versión que leímos
result = mcp_checkpoint_set_state(
    key="workflow:plan-hoy",
    value=json.dumps(plan),
    expected_version=current["version"]  # ← guardia OCC
)

if result["status"] == "conflict":
    # Otro agente cambió el estado → releer y reintentar
    pass
elif result["status"] == "ok":
    # Cambio exitoso, nueva versión asignada
    print(f"Checkpoint actualizado, versión {result['version']}")
```

Cada escritura lleva la versión observada al leer. Si otro agente cambió la clave en el medio, el write falla con `conflict` — relees y reintentas. Este es el patrón estándar de **Optimistic Concurrency Control (OCC)**, el mismo que usan sistemas como Elasticsearch, CouchDB y Git.

### Patrón 3: Lock Distribuido

```python
# Intentar adquirir un lock (create-only)
result = mcp_checkpoint_set_state(
    key="lock:db-migration",
    value=json.dumps({"owner": "agent-A", "acquired_at": "..."}),
    expected_version=0  # ← solo funciona si NO existe
)

if result["status"] == "ok":
    # Lock adquirido — ejecutar operación crítica
    run_migration()
    # Liberar
    mcp_checkpoint_delete_state(key="lock:db-migration")
else:
    # Lock tomado por otro — esperar o abortar
    pass
```

### Patrón 4: Skip si ya se hizo (idempotencia)

```python
# Antes de arrancar: ¿el trabajo ya se completó?
state = mcp_checkpoint_get_state(key="checkpoint:emitir-facturas")
if state["status"] != "not_found":
    print("Trabajo ya completado, saltando")
    return

# Claim + ejecutar
mcp_checkpoint_force_set_state(
    key="checkpoint:emitir-facturas",
    value='{"status": "started"}'
)
# ... hacer el trabajo ...
```

---

## 📐 Convención de Nombres de Claves

Usa esta estructura para mantener las claves organizadas:

```
<dominio>:<identificador>[:<atributo>]
```

| Ejemplo | Propósito |
|---------|-----------|
| `workflow:daily-digest` | Estado de un workflow multi-paso |
| `project:agentcheckpoint:build-status` | Estado de build de un proyecto |
| `lock:database-migration` | Mutex para operación crítica |
| `plan:2026-06-16` | Plan de ejecución diario |
| `checkpoint:nocturno-pilar-1` | Checkpoint de worker nocturno |
| `cron:noticias-manana` | Coordinación de cron job |

**Buenas prácticas:**
- Usa dos puntos (`:`) como separadores — son legibles y funcionan con `SELECT LIKE`
- No superes los **200 caracteres** por clave
- Los valores **siempre deben ser JSON válido**
- Usa `list_state(pattern="project:%")` para encontrar todas las claves de un dominio

---

## 📊 API de Referencia

### `get_state(key)`

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `key` | `string` | ✅ | Clave a leer |

**Respuesta exitosa:**
```json
{"status": "ok", "key": "workflow:plan", "value": "...", "version": 3, "updated_at": "2026-06-16T..."}
```

**Clave inexistente:**
```json
{"status": "not_found", "key": "workflow:plan"}
```

### `set_state(key, value, expected_version?)`

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `key` | `string` | ✅ | Clave a escribir |
| `value` | `string` | ✅ | Valor (JSON string) |
| `expected_version` | `integer` | ❌ | -1=incondicional (predeterminado), 0=solo crear, N=update versionado |

**Comportamiento del version guard:**
| `expected_version` | Resultado |
|--------------------|-----------|
| `-1` (omitido) | Escribe siempre (como `force_set_state`) |
| `0` | Crea solo si NO existe. Falla con `conflict` si ya existe |
| `N > 0` | Actualiza solo si la versión almacenada coincide con N. Falla con `conflict` si no coincide |

### `force_set_state(key, value)`

Incondicional. Siempre escribe. No tiene version guard.

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `key` | `string` | ✅ | Clave a escribir |
| `value` | `string` | ✅ | Valor (JSON string) |

### `list_state(pattern?)`

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `pattern` | `string` | ❌ | Patrón SQL LIKE (`%` = cualquier texto, `_` = un caracter). Predeterminado: `%` |

### `delete_state(key)`

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `key` | `string` | ✅ | Clave a eliminar |

---

## ⚙️ Configuración

| Variable de entorno | Predeterminado | Descripción |
|--------------------|----------------|-------------|
| `CHECKPOINT_DB_PATH` | `~/.hermes/checkpoints.db` | Ruta del archivo SQLite |

Ejemplo con ruta personalizada:

```bash
CHECKPOINT_DB_PATH=/tmp/mi-estado.db agentcheckpoint
```

---

## 🏗️ Arquitectura

```
┌──────────────────────┐       stdio (stdin/stdout)      ┌────────────────────┐
│                       │                                  │                    │
│  Cliente MCP          │ ────── JSON-RPC (MCP) ───────→  │  agentcheckpoint   │
│  (Claude, Cursor,     │ ←────────────────────────────── │  Servidor MCP      │
│   Windsurf, Hermes)   │                                  │                    │
│                       │                                  │  ┌──────────────┐  │
└──────────────────────┘                                  │  │  SQLite WAL   │  │
                                                          │  │  state.db     │  │
                                                          │  │  (1 archivo)  │  │
                                                          │  └──────────────┘  │
                                                          └────────────────────┘
```

### Detalles técnicos

- **Transporte:** stdio (MCP subprocess) — sin puertos de red, sin contenedores
- **Base de datos:** SQLite en modo WAL (Write-Ahead Logging) para lecturas concurrentes sin bloqueos
- **Concurrencia:** `PRAGMA synchronous=NORMAL` — balance entre durabilidad y velocidad
- **Validación:** todo valor se valida como JSON al escribirse
- **Versionado:** cada UPSERT incrementa el contador de versión atómicamente
- **Timeout de conexión:** 5 segundos en SQLite, 10 segundos recomendados en el cliente MCP
- **Atomicidad:** las escrituras son transaccionales — o se persisten completas o no se persisten

---

## ❓ FAQ

**P: ¿AgentCheckpoint reemplaza a agentmemory?**
R: No. Son herramientas complementarias. AgentCheckpoint coordina estado (¿quién hizo qué? ¿en qué paso vamos?). agentmemory guarda hechos y aprendizajes (¿qué descubrimos? ¿cómo funciona X?). **Úsalos juntos.**

**P: ¿Puedo tener múltiples instancias apuntando al mismo archivo?**
R: Técnicamente SQLite WAL soporta múltiples lectores concurrentes, pero para escritores múltiples es mejor usar una sola instancia del servidor MCP. Si necesitas alta disponibilidad, considera poner el `.db` en un volumen compartido.

**P: ¿Qué pasa si el proceso se cae a la mitad de una escritura?**
R: SQLite WAL garantiza atomicidad — o se persiste el cambio completo, o no se persiste nada. No hay escrituras parciales.

**P: ¿Cuánto puede medir un valor?**
R: Los valores son strings JSON. SQLite puede manejar valores de hasta ~1GB teóricamente, pero te recomiendo mantenerlos por debajo de **100KB**. Para datos grandes, guarda una referencia (ruta de archivo, URL) como valor.

**P: ¿Y si necesito limpiar checkpoints viejos?**
R: Puedes usar `delete_state` para claves individuales o escribir un script que itere con `list_state` y borre según el `updated_at`.

**P: ¿Soporta TTL / expiración automática?**
R: No de forma nativa, pero puedes implementarlo en tu agente: al leer, verifica el `updated_at` y decide si el estado está vencido.

---

## 🧑‍💻 Desarrollo

```bash
git clone https://github.com/erniomaldo/agentcheckpoint
cd agentcheckpoint
pip install -e ".[dev]"
```

El código fuente está en `src/agentcheckpoint/`:

| Archivo | Lo que hace |
|---------|-------------|
| `__init__.py` | Versión del paquete |
| `__main__.py` | Entry point (`python -m agentcheckpoint`) |
| `server.py` | Servidor MCP completo (~150 líneas) |

### Cómo contribuir

1. Haz un fork del repositorio
2. Crea una rama (`git checkout -b feature/algo-genial`)
3. Haz tus cambios
4. Confirma con mensajes claros
5. Haz push y abre un Pull Request

---

## 📜 Licencia

MIT © [Ernesto Maldonado](https://github.com/erniomaldo)

---

## 🌐 Idiomas

| Idioma | Archivo |
|--------|---------|
| 🇺🇸 English | [`README.md`](README.md) |
| 🇪🇸 Español | `README.es.md` (este) |
| 🇫🇷 Français | [`README.fr.md`](README.fr.md) |
| 🇧🇷 Português | [`README.pt.md`](README.pt.md) |

---

<p align="center">
  <sub>Hecho con ❤️ para que los agentes no pisen el estado de otros agentes.</sub><br>
  <sub>¿Te sirvió? Deja una ⭐ en <a href="https://github.com/erniomaldo/agentcheckpoint">GitHub</a></sub>
</p>
