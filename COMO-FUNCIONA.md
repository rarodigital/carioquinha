# carioquinha — Manual Técnico Completo

> **Público:** desenvolvedores e agentes de IA que precisam **entender, operar,
> reproduzir ou estender** o sistema sem ambiguidade. Este documento é a fonte de
> verdade sobre arquitetura, contratos, formatos de dados, invariantes de
> segurança e procedimentos operacionais.
>
> **Repositório:** `rarodigital/carioquinha` · **Estado:** memória por-usuário,
> onboarding, captura contínua, permissões por papel, sandbox (bubblewrap) e
> staging de anexos, todos ativos.

---

## 0. Glossário e princípios inegociáveis

| Termo | Definição precisa |
|---|---|
| **carioquinha** | Este repositório. Camada de **memória + identidade + permissões**. NÃO é uma IA. |
| **Inteligência / agente** | O **Claude Code**, que executa via plugin do Telegram. É quem raciocina e usa ferramentas. |
| **Ponte** | O plugin `telegram@claude-plugins-official` do Claude Code, sob o serviço systemd `claude-telegram.service`. |
| **requester** | A pessoa que enviou a mensagem no turno atual (resolvida em pessoa/canal/papel). |
| **key (chave de memória)** | String `"<pessoa>-<canal>"` que identifica um cérebro isolado em disco. |
| **workspace** | Diretório de escrita livre de um NÃO-ADMIN: `workspaces/<slug(pessoa)>/`. |
| **admin / normal** | Papéis. `admin` = acesso total (VPS incluída). `normal` = confinado ao próprio workspace. |

**Princípios (não violar):**
1. **Não alterar o nserver.** `agente/agent.py` e `agente/onboarding.py` do
   `/root/nserverlbot` permanecem intactos. O carioquinha vive FORA desse repo.
2. **Segurança por hook, não por confiança.** As restrições de não-admin são
   impostas por hooks do Claude Code que podem **negar** ou **reescrever** ações,
   não por instruções ao modelo.
3. **Falha segura no terminal.** Sem estado resolvido, assume-se admin/terminal
   (a máquina é do administrador) — para nunca travar o operador local.
4. **Isolamento de memória por pessoa × canal** por padrão.

---

## 1. Arquitetura em camadas

```
┌─────────────────────────────────────────────────────────────────┐
│ PESSOA (Telegram / terminal)                                     │
└───────────────┬─────────────────────────────────────────────────┘
                │ mensagem
┌───────────────▼─────────────────────────────────────────────────┐
│ CLAUDE CODE (a inteligência)  —  serviço systemd claude-telegram │
│                                                                  │
│  hooks disparados pelo harness (config em ~/.claude/settings.json)│
│   • UserPromptSubmit → hooks/on_prompt.py                        │
│   • PreToolUse        → hooks/guard.py                           │
│   • PostToolUse       → hooks/stage_download.py                  │
└───────────────┬─────────────────────────────────────────────────┘
                │ import
┌───────────────▼─────────────────────────────────────────────────┐
│ carioquinha.py  (identidade/canal/papel, estado por sessão,      │
│                  workspaces, staging)                            │
│        │ import                                                  │
│        ▼                                                         │
│ userbrain.py    (perfil USER.md, memória, captura contínua)      │
│ sandbox.py      (jaula bubblewrap para shell de não-admin)       │
└───────────────┬─────────────────────────────────────────────────┘
                │ leitura/escrita
┌───────────────▼─────────────────────────────────────────────────┐
│ DISCO:  data/users/<key>/…   e   workspaces/<slug>/…             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Layout do repositório (com papel de cada arquivo)

```
carioquinha/
├── COMO-FUNCIONA.md          # este manual
├── README.md                 # uso rápido + instalação dos hooks
├── userbrain.py              # LIB: perfil (USER.md) + memória + captura contínua
├── carioquinha.py            # LIB: identidade/papel/canal, estado/sessão, anexos, workspaces
├── onboarding.py             # LIB: fluxo de onboarding (transporte-agnóstico)
├── sandbox.py                # LIB: jaula bubblewrap para shell de não-admin
├── seed_registered.py        # SCRIPT: cria USER.md para usuários já cadastrados no nserver
├── demo.py                   # SCRIPT: demonstração ponta a ponta
├── identities.example.json   # modelo do mapa de identidades
├── identities.json           # REAL (IDs pessoais) — IGNORADO pelo Git
├── hooks/
│   ├── on_prompt.py          # HOOK UserPromptSubmit
│   ├── guard.py              # HOOK PreToolUse
│   └── stage_download.py     # HOOK PostToolUse
├── data/                     # runtime: memórias e estado — IGNORADO pelo Git
└── workspaces/               # runtime: arquivos dos usuários — IGNORADO pelo Git
```

`.gitignore` cobre: `__pycache__/`, `*.pyc`, `data/`, `workspaces/`, `identities.json`.

---

## 3. Módulo `userbrain.py` — perfil e memória

### 3.1 Configuração e constantes
- `DATA_ROOT` = env `USERBRAIN_DATA` ou `<repo>/data`.
- `USERS_ROOT` = `DATA_ROOT/users`.
- `PROFILE_FIELDS` (ordem = ordem no USER.md):
  `chamar` (Como chamar), `nome_completo` (Nome completo), `trabalho`
  (Trabalho / o que faz), `interesses` (Interesses), `pedidos_comuns`
  (Pedidos comuns ao bot), `estilo` (Como gosta de ser tratado), `idioma`
  (Idioma), `fuso` (Fuso horário).

### 3.2 Estrutura em disco de um cérebro
```
data/users/<slug>/
├── USER.md                 # perfil estruturado da PESSOA (markdown com campos "- **Label:** valor")
├── IDENTITY.md             # persona do agente para a pessoa
├── memory/
│   ├── facts.md            # memória de LONGO PRAZO (sempre no contexto)
│   └── {YYYY-MM-DD}.md     # daily notes (histórico)
├── .onboarding.json        # (escrito por onboarding.py) estado do fluxo
└── .onboarded              # (escrito por onboarding.py) marcador de conclusão
```
`<slug>` = `user_slug(name)`: minúsculas/números/`._-` preservados; demais
caracteres viram `-`; truncado em 80; vazio → `"default"`.

### 3.3 API pública
| Função | Assinatura | Efeito |
|---|---|---|
| `user_slug` | `(name)->str` | normaliza nome para pasta |
| `user_dir` / `memory_dir` | `(name)->Path` | caminhos do cérebro |
| `ensure_user` | `(name)->Path` | cria pasta + USER.md/IDENTITY.md/facts.md se faltarem (idempotente) |
| `read_profile_text` | `(name)->str` | conteúdo do USER.md |
| `get_profile` | `(name)->dict` | campos preenchidos `{key: valor}` |
| `set_profile_field` | `(name, key, value)->None` | grava/atualiza um campo (valida `key`) |
| `append_profile_field` | `(name, key, value)->bool` | acrescenta item sem duplicar (ex.: interesses) |
| `observe` | `(name, text)->list[str]` | **captura contínua** (ver 3.4) |
| `remember` | `(name, note, kind="daily"|"fact")->Path` | grava memória persistente |
| `long_term` | `(name)->str` | conteúdo de facts.md |
| `recent_daily` | `(name, days=2, max_chars=4000)->str` | últimas daily notes |
| `context` | `(name)->str` | **bloco de contexto** (USER.md + facts.md + daily) |
| `list_users` | `()->list[str]` | slugs existentes |

### 3.4 Captura contínua (`observe`)
Regex conservadoras em `_CAPTURE_PATTERNS`. Só captura auto-revelação explícita:
- `chamar` (set): "me chama de X", "pode me chamar de X", "meu nome é X".
- `trabalho` (set): "trabalho com X", "sou <profissão>".
- `interesses` (append): "gosto de/curto/amo/adoro X".
- `estilo` (set): "prefiro/quero/responde/responda … X".
- `fuso` (set): "moro/estou/tô em X".

Remove filler final ("também", "agora", "tbm", "tá", "né"…). Toda mudança também
vira uma linha em `facts.md`. Retorna a lista de mudanças (ex.: `["trabalho = marketing digital"]`)
ou `[]`.

### 3.5 `context(name)` — formato de saída
```
## Perfil do usuário (USER.md)
<conteúdo de USER.md>

## Memória de longo prazo (facts.md)
<conteúdo de facts.md>

## Memória recente (daily notes)      ← só se houver
<últimas daily notes>
```

---

## 4. Módulo `carioquinha.py` — identidade, papel, canal, sessão

### 4.1 Configuração
- `IDENTITIES` = `<repo>/identities.json`.
- `WORKSPACES_ROOT` = env `CARIOQUINHA_WORKSPACES` ou `<repo>/workspaces`.
- Estado por sessão em `DATA_ROOT/.active-<session_id_sanitizado>.json`.

### 4.2 Formato de `identities.json`
```json
{
  "terminal_person": "adalto",
  "admins": ["7403271687"],
  "people": { "7403271687": "adalto", "207597739": "rafaela" }
}
```
- `terminal_person`: nome da pessoa quando o canal é `terminal`.
- `admins`: lista de IDs (string) com papel `admin`.
- `people`: mapa `id_bruto -> nome da pessoa`.

### 4.3 Resolução — `resolve(channel, raw_user) -> dict`
Retorna `{channel, raw, person, role, key}`.
- `channel == "terminal"` → `person=terminal_person`, `role="admin"`, `key="<person>-terminal"`.
- Caso contrário: `person = people[raw]` ou fallback `"<canal[:2]>-<raw|anon>"`
  (ex.: `te-999888`); `role="admin"` se `raw ∈ admins`, senão `"normal"`;
  `key="<person>-<channel>"`.

### 4.4 Parsing do harness
A mensagem do harness pode conter a tag `<channel …>`. Helpers:
- `parse_prompt(prompt) -> (channel, raw_user)`: sem tag → `("terminal","")`.
  Telegram prioriza `chat_id`, senão `user`.
- `strip_tags(text) -> str`: remove a tag para a captura só ver o texto humano.
- `parse_attachments(prompt) -> list[str]`: extrai caminhos locais **existentes**
  dos atributos `image_path`, `attachment_path`, `document_path`, `file_path`.

### 4.5 Estado por sessão (evita conflito terminal × Telegram)
- `set_active(info, session_id)` / `get_active(session_id)`.
- **Invariante:** `on_prompt.py` grava o estado ANTES de qualquer ferramenta do
  turno; `guard.py` lê pelo mesmo `session_id`. Como cada processo Claude Code tem
  `session_id` próprio, terminal e Telegram não colidem. Default (sem arquivo) =
  admin/terminal.

### 4.6 Workspaces e staging
- `workspace_dir(person) -> Path`: `WORKSPACES_ROOT/<slug(person)>` (cria se faltar).
  **Chave:** workspace é por **pessoa** (não por canal), então os arquivos dela
  são os mesmos no Telegram e no web.
- `stage_files(paths, person) -> list[str]`: copia (`shutil.copy2`) anexos para o
  workspace; devolve os nomes copiados.

---

## 5. Módulo `sandbox.py` — jaula de shell (bubblewrap)

### 5.1 Objetivo
Permitir que o NÃO-ADMIN rode **qualquer** shell (editar foto, `python`, `curl`,
instalar libs no venv dele, integrações) **sem** conseguir ler segredos nem
alterar a VPS.

### 5.2 Composição da jaula — `wrap_argv(command, workspace)`
```
bwrap
  --ro-bind / /                      # raiz inteira somente-leitura (bins/libs ok)
  --tmpfs /root --tmpfs /home        # ESCONDE segredos, nserver e outros usuários
  --tmpfs /opt  --tmpfs /tmp         # (escrita nessas viadas é efêmera/isolada)
  --proc /proc --dev /dev
  --bind <ws> <ws>                   # ÚNICA escrita real persistente = workspace
  --chdir <ws> --setenv HOME <ws>
  --unshare-all --share-net          # isola namespaces; mantém REDE
  --die-with-parent --new-session
  /usr/bin/bash -c "<command>"
```
- `wrap_command(command, ws) -> str`: mesma coisa como **string de shell segura**
  (via `shlex.quote`), pronta para virar o campo `command` da tool Bash.
- `HIDE = ["/root", "/home", "/opt", "/tmp"]`. Ordem importa: `--ro-bind / /`
  primeiro; os `--tmpfs` sobrepõem/escondem; `--bind <ws>` recria o workspace
  gravável por cima da tmpfs de `/root` (o workspace fica sob `/root/...`).

### 5.3 Garantias verificadas (`python3 sandbox.py --selftest`)
| Teste | Resultado esperado |
|---|---|
| escrever no workspace | OK |
| escrever no nserver/VPS | falha; arquivo real intacto |
| ler `/root/.gh_token` e afins | invisível (No such file) |
| rodar `python3`, `curl` | OK; rede OK |

### 5.4 Requisito
`bwrap` (bubblewrap) instalado no host (`apt-get install -y bubblewrap`; versão
usada: 0.9.0). Sem ele, o `guard.py` **nega** o shell do não-admin (falha segura).

---

## 6. Módulo `onboarding.py` — primeiro contato

Transporte-agnóstico: `handle(text, name) -> (replies: list[str], done: bool)`.
- Primeiro contato (sem `.onboarded`) → dispara `begin` (mensagem de boas-vindas).
- Passos: `identity` → grava `IDENTITY.md` (+ apelido no USER.md se detectado) →
  `about` → grava `trabalho` + fato → `style` → grava `estilo` + fato → `.onboarded`.
- Gatilhos de reinício: "personalizar", "startkit", "refazer identidade",
  "criar identidade". Pular: "pular", "depois", "agora não", "skip".
- `needs_onboarding(name) -> bool` = ausência de `.onboarded`.

> Observação: no fluxo de produção (Claude Code + Telegram), o onboarding pode ser
> conduzido pela própria IA usando as libs; `onboarding.py` fornece o roteiro
> canônico e é usado tal-e-qual em integrações que queiram um fluxo determinístico.

---

## 7. Hooks — contratos exatos (entrada/saída)

Todos os hooks: **stdin = JSON do harness**; **stdout = JSON de controle** (ou
vazio); qualquer exceção → `exit 0` silencioso (falha segura). Registrados em
`~/.claude/settings.json` (ver §8).

### 7.1 `hooks/on_prompt.py` — evento `UserPromptSubmit`
**Entrada (campos usados):** `prompt` (ou `user_prompt`/`message`), `session_id`.
**Ações:**
1. `channel, raw = parse_prompt(prompt)`; `info = resolve(...)`; `set_active(info, session_id)`.
2. `ensure_user(key)`; `observe(key, strip_tags(prompt))` (captura contínua).
3. Se `role == normal`: `stage_files(parse_attachments(prompt), person)` (staging de anexos).
4. Monta `nota` (quem é, papel, memória; se normal, regras do workspace) + `context(key)`.

**Saída:**
```json
{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"<nota>\n\n<context>"}}
```
`additionalContext` é injetado no contexto do turno — é como a IA "sabe" quem é o
usuário e o que pode/não pode.

### 7.2 `hooks/guard.py` — evento `PreToolUse`
**Matcher:** `Read|Glob|Grep|Bash|Edit|Write|NotebookEdit|MultiEdit`.
**Entrada:** `tool_name`, `tool_input`, `session_id`.
**Lógica:**
1. `active = get_active(session_id)`. Se `role == admin` → **allow** (`exit 0`).
2. NÃO-ADMIN:
   - `tool ∈ {Read,Glob,Grep,Edit,Write,NotebookEdit,MultiEdit}` (PATH_SCOPED):
     extrai caminhos de `file_path`/`notebook_path`/`path`. Sem caminho → **deny**.
     Se **todos** os caminhos resolvidos estão dentro de `workspace_dir(person)` →
     **allow**; senão → **deny** (com motivo).
   - `tool == Bash`: pega `command`; `wrapped = sandbox.wrap_command(command, ws)`;
     retorna **allow + `updatedInput`** com `command = wrapped` (jaula). Se o
     confinamento falhar → **deny**.
   - Outras ferramentas → **allow**.

**Formato de negação:**
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"<motivo>"}}
```
**Formato de liberação com reescrita (Bash confinado):**
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"...","updatedInput":{"command":"bwrap … -c '<cmd original>'"}}}
```

### 7.3 `hooks/stage_download.py` — evento `PostToolUse`
**Matcher:** `.*download.*attachment.*` (ex.: `mcp__…__download_attachment`).
**Entrada:** `tool_response`, `session_id`. Admin → no-op.
**Ação:** varre `tool_response` por caminhos de arquivo existentes fora do
workspace; copia para `workspace_dir(person)`; injeta `additionalContext` avisando
o novo caminho.
**Saída (se copiou):**
```json
{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"[carioquinha] Anexo(s) copiado(s) para o workspace de <p>: <arqs> (em <ws>). Trabalhe a partir dai."}}
```

---

## 8. Configuração no Claude Code (`~/.claude/settings.json`)

### 8.1 Bloco de hooks (exato)
```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "python3 /root/user-brain-kit/hooks/on_prompt.py", "timeout": 15 } ] }
    ],
    "PreToolUse": [
      { "matcher": "Read|Glob|Grep|Bash|Edit|Write|NotebookEdit|MultiEdit",
        "hooks": [ { "type": "command", "command": "python3 /root/user-brain-kit/hooks/guard.py", "timeout": 10 } ] }
    ],
    "PostToolUse": [
      { "matcher": ".*download.*attachment.*",
        "hooks": [ { "type": "command", "command": "python3 /root/user-brain-kit/hooks/stage_download.py", "timeout": 10 } ] }
    ]
  }
}
```

### 8.2 Permissões
- **`bypassPermissions` (modo livre global) foi REMOVIDO** — perigoso em cenário
  multiusuário.
- `permissions.allow` = `["mcp__claude_ai_ClickUp","Bash","Edit","Write"]`. A
  allow-list evita prompts para o admin; o `guard.py` é quem barra o não-admin.

### 8.3 Regra de recarga (importante)
- **Conteúdo dos scripts** `.py` é relido a cada execução → editar lógica de hook
  **não** exige reiniciar o bot.
- **Config** (quais tools/matchers/eventos disparam hook) só é lida na inicialização
  → mudar o bloco de hooks EXIGE **reiniciar** o serviço (§9).

---

## 9. Operação (produção)

### 9.1 Serviço
```
systemd: claude-telegram.service
ExecStart=/usr/bin/script -q -c "/root/.local/bin/claude --channels plugin:telegram@claude-plugins-official" /dev/null
Restart=always
```
Reiniciar (recarrega settings.json / hooks):
```bash
systemctl restart claude-telegram.service
```
Após reiniciar, verificar que há **apenas um** processo de bridge:
```bash
ps -o pid,etimes,cmd -C claude | grep -- '--channels'
```
> Cuidado: processos `claude --channels …` órfãos (fora do systemd) devem ser
> mortos — um bridge duplicado responderia SEM os hooks. Nunca matar a própria
> sessão de terminal (`claude` sem `--channels`).

### 9.2 Cadastrar/ajustar pessoas
Editar `identities.json` (não versionado): adicionar `id -> nome` em `people` e o
`id` em `admins` se for administrador. Efeito imediato (o resolvedor relê o arquivo).

---

## 10. Modelo de segurança — invariantes

1. **Admin** (terminal, ou Telegram cujo `chat_id ∈ admins`) → sem restrição de hook.
2. **Não-admin**:
   - Leitura e escrita de arquivos **somente** dentro de `workspaces/<pessoa>/`.
   - Shell **sempre** confinado por bubblewrap ao workspace; sem leitura de
     `/root` (segredos, nserver), `/home`, `/opt`; escrita real só no workspace.
   - Sem `bwrap` disponível → shell **negado** (nunca liberado sem confinamento).
3. **Isolamento de sessão:** estado do requester é por `session_id`; turnos são
   processados serialmente dentro de cada processo Claude Code.
4. **Falha segura:** exceção em hook nunca trava o turno; ausência de estado assume
   admin/terminal (operador local).

### 10.1 Pontos a endurecer / verificar (limitações conhecidas)
- **`updatedInput` ao vivo:** confirmar, com uma mensagem real de Telegram de um
  não-admin, que o harness aplica o comando reescrito (jaula). Lógica e jaula já
  testadas isoladamente.
- **`stage_download.py`:** é best-effort — depende do formato de resposta do
  `download_attachment`; validar com um envio de documento real.
- **Leitura via shell dentro da jaula:** a jaula roda como root e o `/etc` fica
  legível (ro). Não há escrita nem acesso a `/root`; para endurecer leitura de
  `/etc`, mapear uid não-privilegiado no bwrap (evolução futura).
- **Web:** hoje é o site do nserver (outro sistema, OpenRouter). Integrá-la ao
  carioquinha exigiria mexer no nserver — deixado para depois.

---

## 11. Testes e verificação

```bash
python3 userbrain.py            # smoke: cria perfil + memória + imprime contexto
python3 carioquinha.py          # imprime resolução de identidade/papel para exemplos
python3 sandbox.py --selftest   # prova de confinamento (escapes)
python3 demo.py                 # onboarding + memória + captura de 2 usuários, ponta a ponta
python3 seed_registered.py      # cria USER.md para usuários já cadastrados no nserver (só leitura do nserver)
```

Testes manuais de hook (simulando o harness):
```bash
# guard nega leitura de segredo por não-admin
python3 -c "import carioquinha as cq; cq.set_active(cq.resolve('telegram','207597739'),'s')"
echo '{"tool_name":"Read","session_id":"s","tool_input":{"file_path":"/root/.gh_token"}}' | python3 hooks/guard.py
```

---

## 12. Como estender (receitas)

- **Novo campo de perfil:** adicione em `userbrain.PROFILE_FIELDS` (key, Label).
  `USER.md` novos já nascem com ele; existentes recebem no próximo `set_profile_field`.
- **Nova regra de captura:** adicione um padrão em `userbrain._CAPTURE_PATTERNS`.
- **Novo papel/permissão:** ajuste `carioquinha.resolve` (mapear papéis) e a lógica
  de `guard.py` (o que cada papel pode).
- **Novo canal (ex.: web real):** faça o canal injetar uma tag `<channel source="web" user="...">`
  e mapeie em `identities.people`. A memória `web` já fica isolada por `key`.
- **Endurecer a jaula:** editar `sandbox.wrap_argv` (ex.: `--unshare-user --uid`,
  esconder mais caminhos, remover `--share-net` quando não precisar de rede).

---

## 13. Contexto do projeto (histórico essencial)

- Origem: pedido de personalizar o onboarding de um bot no Telegram, inspirado no
  zip "Cérebro Pessoal Pixel" (camada sobre OpenClaw v2).
- Decisão de arquitetura: a inteligência é o **Claude Code** (como no
  "institutotheronbot"); o carioquinha entra como **memória + permissões**.
- Restrições fixadas pelo administrador (**Adalto**, Telegram *nydollar* =
  `7403271687`): não tocar no nserver; só admin mexe na VPS; não-admin com
  liberdade total apenas no próprio workspace; memórias separadas por canal.

---

*Fim do manual. Mantenha este documento em sincronia com o código — ele é a fonte
de verdade para humanos e IAs que forem operar ou estender o carioquinha.*
