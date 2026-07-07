# user-brain-kit

Cérebro por-usuário para bots: **perfil estruturado (`USER.md`) + memória
persistente + memória de longo prazo**, com onboarding conversacional no primeiro
contato. Cada pessoa que fala com o bot ganha o próprio workspace, e o bot passa a
**conhecer e responder de forma personalizada** a cada uma.

Espelhado no `onboarding.py` do **nserverlbot** e na camada "Cérebro Pessoal" da
**Pixel** (OpenClaw v2) — mas **autônomo**: não importa nem altera o nserver. É a
semente de um repositório próprio.

## Ideia central

O nserver hoje mistura duas coisas: a persona do agente (`IDENTITY.md`) e o que
sabe da pessoa (nota solta na memória). Aqui separamos:

| Arquivo | Descreve | Papel |
|---|---|---|
| `USER.md` | quem é a **pessoa** | perfil estruturado, sempre no contexto |
| `IDENTITY.md` | quem é o **agente** para essa pessoa | persona (nome, vibe, emoji) |
| `memory/facts.md` | fatos duráveis | **memória de longo prazo**, sempre no contexto |
| `memory/{YYYY-MM-DD}.md` | daily notes | **memória persistente** do dia-a-dia |

## Estrutura em disco

```
data/users/<slug>/
├── USER.md
├── IDENTITY.md
├── memory/
│   ├── facts.md
│   └── {YYYY-MM-DD}.md
├── .onboarding.json   # estado do onboarding em andamento
└── .onboarded         # marcador de conclusão
```

Raiz dos dados configurável via env `USERBRAIN_DATA` (default: `./data`).

## Uso

```python
import userbrain as ub
import onboarding

# Primeiro contato: dispara o onboarding (transporte-agnóstico)
replies, done = onboarding.handle("", "Rafael")
for r in replies:
    enviar_ao_usuario(r)

# Mensagens seguintes até done=True vão preenchendo USER.md + memória
replies, done = onboarding.handle(texto_do_usuario, "Rafael")

# Depois do onboarding: monta o contexto por-usuário (vira system prompt)
system_prompt = ub.context("Rafael")

# Memória a qualquer momento
ub.remember("Rafael", "Prefere respostas curtas.", kind="fact")   # longo prazo
ub.remember("Rafael", "Pediu deploy do bot.", kind="daily")       # persistente
ub.set_profile_field("Rafael", "interesses", "café, edição de vídeo")
```

### Captura contínua (o perfil aprofunda sozinho)

Passe **toda mensagem normal** por `observe()`. Quando a pessoa se revela
("me chama de X", "trabalho com Y", "gosto de Z"), o perfil é atualizado
sozinho — reativo, sem comando manual e sem adivinhar:

```python
mudou = ub.observe("Rafael", texto_do_usuario)   # ex.: ["trabalho = marketing digital"]
# 'mudou' é [] quando não há auto-revelação; o bot pode confirmar em 1 linha se quiser.
```

## Scripts

| Comando | O que faz |
|---|---|
| `python3 demo.py` | Simula 2 usuários, roda o onboarding completo e mostra o contexto de cada um. |
| `python3 seed_registered.py` | Cria `USER.md` para os usuários já cadastrados no nserver (lê só-leitura; não altera o nserver). Ajuste `NSERVER_ROOT` se necessário. |
| `python3 userbrain.py` | Smoke test da biblioteca. |

## Integração num bot (esboço)

No handler de mensagem, logo após identificar o usuário:

```python
replies, done = onboarding.handle(texto, nome_usuario)
if not done:
    for r in replies:
        enviar(r)
    return                     # ainda no onboarding
# fluxo normal, já com contexto personalizado:
system_prompt = userbrain.context(nome_usuario)
```

## Multiusuário no Claude Code (Telegram + terminal)

Camada que liga o carioquinha ao Claude Code para atender **várias pessoas** com
memória separada e **permissões por papel**, sem confiar só em instrução.

| Peça | Arquivo | Função |
|---|---|---|
| Identidades | `identities.json` (real, fora do Git) / `identities.example.json` | mapeia `telegram_id → pessoa` e quem é **admin** |
| Resolvedor | `carioquinha.py` | descobre pessoa/canal/papel e a chave de memória `<pessoa>-<canal>` |
| Hook de entrada | `hooks/on_prompt.py` (UserPromptSubmit) | carrega a memória da pessoa, injeta no contexto e captura fatos novos |
| Guardrail | `hooks/guard.py` (PreToolUse) | **bloqueia** shell/edição/git/VPS para não-admin |

**Memória por pessoa + canal:** `adalto-telegram`, `rafaela-telegram`,
`adalto-terminal`… ficam separados por padrão (mesmo repositório `data/`), então
Telegram ≠ Web ≠ terminal. Dá pra "linkar" depois se quiserem compartilhar.

**Papéis:**
- **admin** (Adalto: terminal + Telegram) → acesso total, inclusive VPS/estrutura.
- **normal** (demais) → chat + memória própria + criativo. Shell, edição de
  arquivo, git/GitHub, deploy e mudanças na VPS são **bloqueados por hook**.

### Instalação dos hooks (no `~/.claude/settings.json`)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "python3 /root/user-brain-kit/hooks/on_prompt.py", "timeout": 15 } ] }
    ],
    "PreToolUse": [
      { "matcher": "Bash|Edit|Write|NotebookEdit|MultiEdit",
        "hooks": [ { "type": "command", "command": "python3 /root/user-brain-kit/hooks/guard.py", "timeout": 10 } ] }
    ]
  }
}
```

> Copie `identities.example.json` para `identities.json` e preencha os IDs reais.

## Não faz (por enquanto)

- Multi-brain (pessoal/empresa/diretoria) e config OpenClaw — ficam para depois.
- Não toca no nserver: `seed_registered.py` só **lê** os diretórios de usuário.
- A **Web** hoje é o site do nserver (outro sistema, OpenRouter). Integrá-la ao
  carioquinha exigiria mexer no nserver — deixado para depois.
