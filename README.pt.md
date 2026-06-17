# AgentCheckpoint

**Armazenamento atômico de chave-valor para coordenação de agentes de IA.**

[![PyPI - Version](https://img.shields.io/pypi/v/agentcheckpoint?style=flat-square&logo=pypi&color=blue)](https://pypi.org/project/agentcheckpoint/)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/agentcheckpoint?style=flat-square&logo=python&color=yellow)](https://pypi.org/project/agentcheckpoint/)
[![License](https://img.shields.io/pypi/l/agentcheckpoint?style=flat-square&color=green)](https://github.com/erniomaldo/agentcheckpoint/blob/main/LICENSE)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/agentcheckpoint?style=flat-square&color=purple)](https://pypistats.org/packages/agentcheckpoint)
[![GitHub Repo Stars](https://img.shields.io/github/stars/erniomaldo/agentcheckpoint?style=flat-square)](https://github.com/erniomaldo/agentcheckpoint)

---

<p align="center">
  <strong>Um servidor MCP que impede seus agentes de trabalharem com estado desatualizado.</strong><br>
  <em>~150 linhas de Python, com SQLite WAL, zero infraestrutura.</em>
</p>

---

🌐 [🇺🇸 English](README.md) · [🇪🇸 Español](README.es.md) · [🇫🇷 Français](README.fr.md)

---

## 📦 Instalação

```bash
pip install agentcheckpoint
```

Em seguida, adicione-o ao seu cliente MCP de preferência (veja [Configuração do Cliente](#-configuração-do-cliente)).

---

## 🤨 O Problema

Memórias semânticas — bancos vetoriais, agentmemory, mem0, etc. — são projetadas para **fatos e aprendizado**, não para **coordenação de estado**. Quando múltiplos agentes leem e escrevem em um estado compartilhado, eis o que acontece:

| Problema | O que acontece | Consequência |
|----------|----------------|--------------|
| `memory.save()` não tem atualização | Cada salvamento cria uma **nova entrada** | Dezenas de versões obsoletas se acumulam |
| `memory.recall()` usa similaridade | Retorna resultados **semanticamente próximos**, não os mais recentes | Agentes leem estado desatualizado |
| Sem controle de concorrência | Dois agentes leem o mesmo estado, escrevem sem coordenação | Alterações se sobrescrevem, perda de dados |
| Sem proteção de versão | Uma escrita pode sobrescrever cegamente o trabalho de outro agente | **Workflows corrompidos, trabalho reexecutado** |

**Conclusão:** seus agentes trabalham com estado desatualizado, reexecutam tarefas já concluídas e queimam recursos em esforço duplicado.

---

## ✅ A Solução

AgentCheckpoint **não** é um armazenamento de memória — é um **armazenamento de estado compartilhado com garantias atômicas**. Pense nele como um semáforo ou memória compartilhada para agentes de IA.

```
┌──────────────────────┐    MCP stdio    ┌────────────────────┐    SQLite WAL    ┌──────────────┐
│  Agente A             │ ───────────────→│                    │ ──────────────→│              │
│  Agente B             │ ───────────────→│  AgentCheckpoint   │ ──────────────→│  state.db    │
│  Trabalhador Cron C   │ ───────────────→│  Servidor MCP      │ ──────────────→│  (1 arquivo) │
│  Pipeline D           │ ←──────────────│                    │ ←──────────────│              │
└──────────────────────┘                  └────────────────────┘                └──────────────┘
```

### Comparação

| Funcionalidade | AgentCheckpoint | agentmemory / banco vetorial | Redis | Arquivo JSON |
|---------------|----------------|------------------------------|-------|--------------|
| **Propósito** | Coordenação de estado | Fatos, aprendizado | Cache genérico | Persistência básica |
| **Escrita** | Sempre substitui (UPSERT) | Sempre adiciona (INSERT) | Sobrescreve (sem versionamento) | Sobrescreve arquivo inteiro |
| **Leitura** | `SELECT WHERE key=?` correspondência exata | `ORDER BY distance` semântico | Busca direta por chave | Analisa e pesquisa |
| **Concorrência** | Controle de Concorrência Otimista (OCC) | Nenhum | Nenhum nativamente | Nenhuma |
| **Persistência** | SQLite WAL (transacional, ACID) | Varia conforme o backend | RAM / RDB / AOF | Dependente do sistema de arquivos |
| **Infraestrutura** | Zero — único processo stdio | Servidor, API, índices | Servidor dedicado | Zero |
| **Ferramentas MCP** | Nativo — autodescoberta de ferramentas | Não | Não | Não |
| **Linhas de código** | ~150 | Milhares | ~50K+ | ~5 (sem garantias) |

**Use ambos juntos:** AgentCheckpoint para estado compartilhado, memória vetorial / agentmemory para fatos, observações e descobertas.

---

## 🛠️ Ferramentas (API MCP)

| Ferramenta | Descrição | Quando usar |
|------------|-----------|-------------|
| `get_state(chave)` | Lê o valor atual, versão e timestamp de uma chave | Antes de qualquer modificação |
| `set_state(chave, valor, versao_esperada?)` | Escreve com proteção de versão opcional (OCC) | Quando **múltiplos** agentes escrevem a mesma chave |
| `force_set_state(chave, valor)` | Escrita atômica incondicional | Quando um **único** agente/trabalhador possui a chave |
| `list_state(padrao?)` | Lista chaves correspondentes a um padrão SQL LIKE | Auditoria, descoberta, depuração |
| `delete_state(chave)` | Remove permanentemente uma chave | Limpeza de estado concluído |

Cada ferramenta é automaticamente descoberta através do protocolo MCP — nenhuma configuração extra é necessária.

> **Nota para clientes MCP:** em alguns clientes, as ferramentas são prefixadas como `mcp_checkpoint_get_state`, `mcp_checkpoint_set_state`, etc.

---

## 🚀 Início Rápido

### 1. Instalação

```bash
pip install agentcheckpoint
# ou com uv:
uv pip install agentcheckpoint
```

### 2. Adicionar ao seu cliente MCP

A configuração varia conforme a plataforma. Após adicionar, **reinicie seu cliente** ou recarregue os servidores MCP.

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

Adicione em `~/.claude/settings.json`:

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

Ou via CLI:

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

Adicione em `~/.continue/config.json`:

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

Adicione em `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  checkpoint:
    command: "agentcheckpoint"
    timeout: 10
```

Em seguida, execute `/reload-mcp` na sessão, ou reinicie o gateway.

#### 🐍 Qualquer cliente com suporte a uvx

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

### 3. Verificação

Pergunte ao seu agente:

> _« Quais ferramentas tenho do servidor MCP checkpoint? »_

Você deve ver todas as 5 ferramentas listadas acima.

### 4. Primeiro checkpoint

```python
# Salvar estado
mcp_checkpoint_force_set_state(
    key="project:build-status",
    value='{"phase": "testing", "passed": 13, "failed": 2}'
)

# Ler estado depois
status = mcp_checkpoint_get_state(key="project:build-status")
# → {status: "ok", key: "...", value: {...}, version: 1, updated_at: "2026-06-16T..."}
```

---

## 🎯 Padrões de Uso

### Padrão 1: Escritor único (tarefas cron, agentes solo)

Use `force_set_state` — sempre bem-sucedido, sempre substitui:

```python
# Trabalhador noturno: registrar progresso
mcp_checkpoint_force_set_state(
    key="checkpoint:nocturnal-2026-06-16",
    value='{"status": "in-progress", "started_at": "2026-06-16T03:00:00Z"}'
)

# ... processamento ...

mcp_checkpoint_force_set_state(
    key="checkpoint:nocturnal-2026-06-16",
    value='{"status": "completed", "records_processed": 1427, "finished_at": "..."}'
)
```

### Padrão 2: Múltiplos agentes com OCC (o mais importante)

Use `get_state` + `set_state` com proteção de versão (Controle de Concorrência Otimista):

```python
# 1. LER com versão
current = mcp_checkpoint_get_state(key="workflow:plan-today")
plan = json.loads(current["value"])
# plan.current_index = 5, version = 3

# 2. MODIFICAR
plan.current_index += 1
plan.current_task = "analysis"

# 3. ESCREVER com a versão que lemos
result = mcp_checkpoint_set_state(
    key="workflow:plan-today",
    value=json.dumps(plan),
    expected_version=current["version"]  # ← proteção OCC
)

if result["status"] == "conflict":
    # Outro agente alterou o estado → reler e tentar novamente
    pass
elif result["status"] == "ok":
    # Escrita bem-sucedida, nova versão atribuída
    print(f"Checkpoint atualizado, versão {result['version']}")
```

Cada escrita carrega a versão observada no momento da leitura. Se outro agente alterou a chave entrementes, a escrita falha com `conflict` — você relê e tenta novamente. Este é o **Controle de Concorrência Otimista (OCC)** padrão, o mesmo padrão usado por Elasticsearch, CouchDB e Git.

### Padrão 3: Trava distribuída

```python
# Tentativa de adquirir uma trava (criação apenas)
result = mcp_checkpoint_set_state(
    key="lock:db-migration",
    value=json.dumps({"owner": "agent-A", "acquired_at": "..."}),
    expected_version=0  # ← só funciona se a chave NÃO EXISTIR
)

if result["status"] == "ok":
    # Trava adquirida — executar operação crítica
    run_migration()
    # Liberar
    mcp_checkpoint_delete_state(key="lock:db-migration")
else:
    # Trava retida por outro — aguardar ou abortar
    pass
```

### Padrão 4: Pular se concluído (proteção de idempotência)

```python
# Antes de começar: isto já foi concluído?
state = mcp_checkpoint_get_state(key="checkpoint:generate-invoices")
if state["status"] != "not_found":
    print("Trabalho já concluído, pulando")
    return

# Reivindicar + executar
mcp_checkpoint_force_set_state(
    key="checkpoint:generate-invoices",
    value='{"status": "started"}'
)
# ... fazer o trabalho ...
```

---

## 📐 Convenção de Nomenclatura de Chaves

Mantenha suas chaves organizadas com esta estrutura:

```
<domínio>:<identificador>[:<atributo>]
```

| Exemplo | Propósito |
|---------|-----------|
| `workflow:daily-digest` | Estado de workflow multi-etapas |
| `project:agentcheckpoint:build-status` | Estado de build de um projeto |
| `lock:database-migration` | Mutex para operação crítica |
| `plan:2026-06-16` | Plano de execução diário |
| `checkpoint:nocturnal-pillar-1` | Checkpoint do trabalhador noturno |
| `cron:news-morning` | Coordenação de tarefa cron |

**Boas práticas:**
- Use dois-pontos (`:`) como separadores — legíveis e funcionam com `SELECT LIKE`
- Mantenha as chaves abaixo de **200 caracteres**
- Valores **devem ser sempre JSON válido**
- Use `list_state(pattern="project:%")` para encontrar todas as chaves de um domínio

---

## 📊 Referência da API

### `get_state(chave)`

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `key` | `string` | ✅ | Chave a ser lida |

**Resposta de sucesso:**
```json
{"status": "ok", "key": "workflow:plan", "value": "...", "version": 3, "updated_at": "2026-06-16T..."}
```

**Chave não encontrada:**
```json
{"status": "not_found", "key": "workflow:plan"}
```

### `set_state(chave, valor, versao_esperada?)`

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `key` | `string` | ✅ | Chave a ser escrita |
| `value` | `string` | ✅ | Valor (string JSON) |
| `expected_version` | `integer` | ❌ | -1=incondicional (padrão), 0=criação apenas, N=atualização versionada |

**Comportamento da proteção de versão:**
| `expected_version` | Resultado |
|--------------------|-----------|
| `-1` (omitido) | Sempre escreve (como `force_set_state`) |
| `0` | Cria apenas se a chave NÃO EXISTIR. Falha com `conflict` se existir |
| `N > 0` | Atualiza apenas se a versão armazenada corresponder a N. Falha com `conflict` se não corresponder |

### `force_set_state(chave, valor)`

Incondicional. Sempre escreve. Sem proteção de versão.

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `key` | `string` | ✅ | Chave a ser escrita |
| `value` | `string` | ✅ | Valor (string JSON) |

### `list_state(padrao?)`

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `pattern` | `string` | ❌ | Padrão SQL LIKE (`%` = qualquer texto, `_` = um caractere). Padrão: `%` |

### `delete_state(chave)`

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `key` | `string` | ✅ | Chave a ser excluída |

---

## ⚙️ Configuração

| Variável de ambiente | Padrão | Descrição |
|---------------------|--------|-----------|
| `CHECKPOINT_DB_PATH` | `~/.hermes/checkpoints.db` | Caminho do arquivo de banco SQLite |

Exemplo de caminho personalizado:

```bash
CHECKPOINT_DB_PATH=/tmp/my-state.db agentcheckpoint
```

---

## 🏗️ Arquitetura

```
┌──────────────────────┐       stdio (stdin/stdout)      ┌────────────────────┐
│                       │                                  │                    │
│  Cliente MCP          │ ────── JSON-RPC (MCP) ───────→  │  agentcheckpoint   │
│  (Claude, Cursor,     │ ←────────────────────────────── │  Servidor MCP      │
│   Windsurf, Hermes)   │                                  │                    │
│                       │                                  │  ┌──────────────┐  │
└──────────────────────┘                                  │  │  SQLite WAL   │  │
                                                          │  │  state.db     │  │
                                                          │  │  (1 arquivo)  │  │
                                                          │  └──────────────┘  │
                                                          └────────────────────┘
```

### Detalhes técnicos

- **Transporte:** stdio (subprocesso MCP) — sem portas de rede, sem contêineres
- **Banco de dados:** SQLite em modo WAL (Write-Ahead Logging) para leituras concorrentes sem bloqueio
- **Concorrência:** `PRAGMA synchronous=NORMAL` — equilíbrio entre durabilidade e velocidade
- **Validação:** todos os valores são validados como JSON na escrita
- **Versionamento:** cada UPSERT incrementa atomicamente o contador de versão
- **Tempo limite de conexão:** 5 segundos no SQLite, 10 segundos recomendado no cliente MCP
- **Atomicidade:** escritas são transacionais — ou totalmente persistidas ou não persistidas

---

## ❓ FAQ

**P: AgentCheckpoint substitui o agentmemory?**
R: Não. Eles são complementares. AgentCheckpoint coordena o estado (quem fez o quê? em qual etapa estamos?). agentmemory armazena fatos e aprendizados (o que descobrimos? como X funciona?). **Use ambos juntos.**

**P: Posso executar várias instâncias apontando para o mesmo arquivo?**
R: SQLite WAL suporta múltiplos leitores concorrentes, mas para múltiplos escritores é melhor usar uma única instância do servidor MCP. Para alta disponibilidade, considere colocar o arquivo `.db` em um volume compartilhado.

**P: O que acontece se o processo travar no meio de uma escrita?**
R: SQLite WAL garante atomicidade — ou toda a alteração é persistida ou nada é. Não há escritas parciais.

**P: Quão grande um valor pode ser?**
R: Valores são strings JSON. SQLite pode teoricamente lidar com até ~1 GB, mas recomendamos manter os valores abaixo de **100 KB**. Para dados grandes, armazene uma referência (caminho de arquivo, URL) como valor.

**P: Como limpar checkpoints antigos?**
R: Use `delete_state` para chaves individuais ou escreva um script que itere com `list_state` e exclua com base em `updated_at`.

**P: O TTL / auto-expiração é suportado?**
R: Não nativamente, mas você pode implementá-lo em seu agente: ao ler, verifique `updated_at` e decida se o estado está desatualizado.

---

## 🧑‍💻 Desenvolvimento

```bash
git clone https://github.com/erniomaldo/agentcheckpoint
cd agentcheckpoint
pip install -e ".[dev]"
```

O código-fonte está em `src/agentcheckpoint/`:

| Arquivo | Função |
|---------|--------|
| `__init__.py` | Versão do pacote |
| `__main__.py` | Ponto de entrada (`python -m agentcheckpoint`) |
| `server.py` | Servidor MCP completo (~150 linhas) |

### Contribuição

1. Faça um fork do repositório
2. Crie uma branch (`git checkout -b feature/awesome-thing`)
3. Faça suas alterações
4. Commit com mensagens claras
5. Push e abra um Pull Request

---

## 📜 Licença

MIT © [Ernesto Maldonado](https://github.com/erniomaldo)

---

## 🌐 Idiomas

| Idioma | Arquivo |
|--------|---------|
| 🇺🇸 English | [`README.md`](README.md) |
| 🇪🇸 Español | [`README.es.md`](README.es.md) |
| 🇫🇷 Français | [`README.fr.md`](README.fr.md) |
| 🇧🇷 Português | `README.pt.md` (este arquivo) |

---

<p align="center">
  <sub>Feito com ❤️ para evitar que agentes pisem no estado uns dos outros.</sub><br>
  <sub>Útil? Deixe uma ⭐ no <a href="https://github.com/erniomaldo/agentcheckpoint">GitHub</a></sub>
</p>
