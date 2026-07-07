# carioquinha — Como tudo funciona

> Documento único explicando **o que é o carioquinha**, **por que ele existe**,
> **como foi construído** e **como cada peça funciona**. Escrito em linguagem
> simples, do começo ao fim.

---

## 1. O que é o carioquinha (em uma frase)

O carioquinha é a **memória de um bot**: ele faz o bot **conhecer cada pessoa**
que fala com ele, **lembrar** das conversas e **responder de forma personalizada**
— com **controle de permissões** para que só o administrador possa mexer no
servidor (VPS), enquanto os outros têm liberdade total só dentro do próprio espaço.

Ele **não é uma inteligência artificial**. Ele é o "caderno de memória" que uma
IA usa. Veja a próxima seção.

---

## 2. As 3 peças de qualquer bot (o conceito mais importante)

Pense num atendente:

| Peça | O que é | No nosso caso |
|---|---|---|
| 🧠 **Inteligência** | quem pensa, escreve código, edita arquivos, monta app | **Claude Code** (a IA) |
| 📒 **Memória** | o caderno com quem é a pessoa e o que já aconteceu | **carioquinha** (este repositório) |
| ☎️ **Ponte** | o canal que liga a pessoa à inteligência | **plugin do Telegram** |

**O carioquinha é a peça do meio (memória).** A inteligência que faz as coisas é
o Claude Code, ligado ao Telegram. O carioquinha entra para dar **memória
persistente por-usuário** e **regras de permissão**.

---

## 3. Memória: separada por pessoa E por canal

Cada pessoa tem seu próprio "cérebro", e cada canal (Telegram, web, terminal) é
separado. A **chave** de memória é `<pessoa>-<canal>`:

```
data/users/adalto-telegram/     ← Adalto no Telegram
data/users/adalto-terminal/     ← Adalto no terminal
data/users/rafaela-telegram/    ← Rafaela no Telegram
```

Assim, **Telegram ≠ Web ≠ terminal** — contexto e memória não se misturam. Tudo
mora no mesmo repositório (`data/`), então dá para "linkar" e compartilhar depois,
se quiserem.

Dentro do cérebro de cada um:

```
data/users/<pessoa>-<canal>/
├── USER.md                 # perfil da PESSOA (como chamar, o que faz, estilo…)
├── IDENTITY.md             # a persona do agente para essa pessoa
└── memory/
    ├── facts.md            # memória de LONGO PRAZO (fatos duráveis, sempre lidos)
    └── {AAAA-MM-DD}.md     # daily notes (memória do dia a dia)
```

- **Memória persistente** = está em disco, sobrevive a reinício.
- **Memória de longo prazo** = `facts.md`, sempre carregado no contexto.

---

## 4. Onboarding: o bot conhece a pessoa no primeiro contato

Na primeira vez que alguém fala, o bot se apresenta e faz 3 perguntinhas
(inspirado no onboarding do nserver, mas próprio e autônomo):

1. Que nome/persona o bot terá, e como chamar a pessoa.
2. O que a pessoa faz / gosta / costuma pedir.
3. Como ela prefere as respostas (curto, detalhado, passo a passo…).

Isso vira um **`USER.md` estruturado**. Depois disso, o bot não repete — ele já
conhece a pessoa. (Código: `onboarding.py`.)

---

## 5. Captura contínua: o perfil aprofunda sozinho

A cada mensagem, o bot presta atenção. Quando a pessoa se revela ("me chama de
Mari", "trabalho com marketing", "gosto de corrida"), o `USER.md` é **atualizado
sozinho** — sem comando. É reativo e conservador (só quando há uma afirmação
clara). (Código: `userbrain.observe()`.)

---

## 6. Permissões: admin vs. normal (o coração da segurança)

- **Admin (Adalto)** — no terminal e no Telegram (conta *nydollar*). Acesso
  **total**, inclusive alterar a VPS/estrutura.
- **Normal (Rafaela e demais)** — **liberdade total dentro do próprio workspace**,
  mas **bloqueados** de tocar na VPS, no sistema, nos segredos ou nos arquivos de
  outras pessoas.

Quem é quem fica em `identities.json` (fora do Git, porque tem IDs pessoais). O
resolvedor é o `carioquinha.py`.

### O que "normal" pode e não pode

| Ação | Dentro do workspace dele | Fora (VPS/sistema/outros) |
|---|---|---|
| Ler arquivos (Read/Glob/Grep) | ✅ pode | ❌ bloqueado |
| Editar/criar (Edit/Write) | ✅ pode | ❌ bloqueado |
| Rodar shell (Bash) | ✅ pode (numa jaula) | ❌ não escapa |
| Conversar / memória própria | ✅ sempre | — |

---

## 7. Como o bloqueio é feito de verdade (hooks)

Não é "confiar na boa vontade da IA" — são **hooks** do Claude Code, que rodam
automaticamente e conseguem **barrar** ações. Três hooks:

| Hook | Quando roda | O que faz |
|---|---|---|
| `hooks/on_prompt.py` | a cada mensagem (UserPromptSubmit) | descobre quem está falando, carrega a memória da pessoa, captura fatos novos e **faz staging de anexos** |
| `hooks/guard.py` | antes de cada ferramenta (PreToolUse) | para não-admin: escopa Read/Edit/Write ao workspace e **confina o Bash** numa jaula; admin passa livre |
| `hooks/stage_download.py` | depois de baixar anexo (PostToolUse) | copia o arquivo baixado para o workspace da pessoa |

Eles ficam registrados no `~/.claude/settings.json` (ver `README.md`). Os scripts
`.py` são relidos a cada execução, então dá para melhorá-los **sem reiniciar** o
bot; só mudar quais tools disparam o hook exige reinício.

---

## 8. A "jaula" (sandbox) — poder total sem risco

Para a Rafaela poder **editar foto, rodar ferramentas e plugar integrações** (tudo
isso precisa de shell) **sem** conseguir mexer na VPS, o shell dela roda dentro de
uma jaula feita com **bubblewrap** (`sandbox.py`):

- a raiz do sistema entra **somente leitura** (os programas funcionam);
- `/root`, `/home`, `/opt`, `/tmp` são **escondidos** (segredos, o nserver e
  outros usuários somem);
- **só o workspace dela** tem escrita real;
- **a rede fica liberada** (para integrações).

Testado com escapes reais: dentro da jaula ela **não altera a VPS**, **não lê os
segredos** (`.gh_token`, chaves SSH), **não enxerga o nserver** — mas roda
`python`, `imagemagick`, `curl` etc. normalmente. (Rode `python3 sandbox.py
--selftest` para ver os testes.)

---

## 9. Staging de anexos — para o bot enxergar o que a pessoa envia

Quando alguém manda uma foto/arquivo no Telegram, ele cai numa pasta de sistema
(inbox) que fica **fora** do workspace — então a jaula e a leitura escopada não
enxergariam. Por isso:

- **Foto** (`image_path`): o `on_prompt.py` **copia para o workspace** na hora.
- **Documento/HTML** (baixado): o `stage_download.py` copia depois do download.

Resultado: "manda um HTML e pede pra editar" → o arquivo é copiado para o
workspace → o bot edita lá dentro → devolve. Tudo confinado.

---

## 10. Estrutura do repositório

```
carioquinha/
├── COMO-FUNCIONA.md          ← este documento
├── README.md                 ← uso rápido + instalação dos hooks
├── userbrain.py              ← biblioteca: perfil (USER.md) + memória + captura
├── onboarding.py             ← fluxo de onboarding (transporte-agnóstico)
├── carioquinha.py            ← identidade/papel/canal + estado por sessão + anexos
├── sandbox.py                ← jaula bubblewrap para shell do não-admin
├── seed_registered.py        ← cria USER.md para usuários já cadastrados no nserver
├── demo.py                   ← demonstração ponta a ponta
├── identities.example.json   ← modelo do mapa de identidades (o real fica fora do Git)
├── hooks/
│   ├── on_prompt.py          ← UserPromptSubmit: memória + captura + staging
│   ├── guard.py              ← PreToolUse: permissões por caminho + jaula
│   └── stage_download.py     ← PostToolUse: staging de anexo baixado
└── data/                     ← memória/workspaces em runtime (fora do Git)
```

---

## 11. Como testar

```bash
python3 demo.py                 # onboarding + memória de 2 usuários, ponta a ponta
python3 sandbox.py --selftest   # prova que a jaula não escapa
python3 seed_registered.py      # cria USER.md dos usuários já cadastrados no nserver
python3 carioquinha.py          # mostra como identidades/papéis são resolvidos
```

---

## 12. Como está ligado no bot (produção)

- O bot é o **Claude Code** rodando com o plugin do Telegram, sob o serviço
  systemd `claude-telegram.service`.
- Os hooks estão em `~/.claude/settings.json` apontando para os scripts deste repo.
- O **modo livre global foi desligado**; a lista de permissões deixa o admin fluido
  e os hooks barram os não-admins.

---

## 13. Regras de projeto (importante)

- **Não mexer no nserver** (`agente/agent.py`, `agente/onboarding.py`): ele continua
  funcionando idêntico. O carioquinha vive **fora** do repositório do nserver.
- A **web** hoje é o site do nserver (outro sistema). Integrá-la ao carioquinha
  exigiria mexer no nserver — ficou para depois.
- **Multi-brain** (pessoal/empresa/diretoria) e configuração do OpenClaw — depois.

---

## 14. O que ainda falta / a verificar

- **Teste ao vivo** com uma pessoa não-admin real: confirmar que o guard aplica o
  comando "embrulhado" (sandbox) numa mensagem de Telegram de verdade.
- **Staging de documento baixado**: o `stage_download.py` é defensivo; falta
  validar o formato exato da resposta do `download_attachment` com um envio real.
- **Bot autônomo 24/7** (opcional): hoje a inteligência é o Claude Code. Se um dia
  quiserem um bot que roda sozinho sem sessão do Claude Code, seria colocar uma IA
  (API) "dentro" do carioquinha — decisão para o futuro.

---

*Repositório: `rarodigital/carioquinha`. Este documento reflete o estado até a
construção da memória por-usuário, permissões por papel, sandbox e staging.*
