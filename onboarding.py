#!/usr/bin/env python3
"""
Onboarding / startkit por-usuário — espelhado no onboarding.py do nserverlbot,
mas autônomo e escrevendo um USER.md estruturado (não uma nota solta na memória).

No primeiro contato de CADA usuário o bot se apresenta, avisa que tem memória e
faz algumas perguntas para (1) montar a persona do agente e (2) montar o perfil
da pessoa (USER.md). A conclusão é marcada por `.onboarded` no cérebro do usuário
— quem já passou não repete.

Transporte-agnóstico: `handle(text, name)` devolve `(replies, done)` — uma lista
de mensagens do bot e um bool. Assim o mesmo fluxo pluga em Telegram, site ou CLI
sem acoplar a nenhum canal.

    import onboarding
    replies, done = onboarding.handle("", "Rafael")   # primeiro contato
    for r in replies: enviar(r)
"""
from __future__ import annotations

import json
import time
from typing import Optional

import userbrain as ub

# Palavras de controle (espelhadas no nserver).
_RESTART_WORDS = {"personalizar", "startkit", "refazer identidade", "criar identidade"}
_SKIP_WORDS = {"pular", "depois", "agora não", "agora nao", "skip"}

WELCOME = (
    "Oi 👋 Essa é a primeira vez que a gente fala.\n\n"
    "Antes de eu sair fazendo coisa, deixa eu me situar. Rapidinho:\n\n"
    "• que nome você quer me dar?\n"
    "• que tipo de criatura eu sou — assistente, copiloto, amigo, fantasma da máquina...\n"
    "• minha vibe — direto, caloroso, técnico, brincalhão?\n"
    "• emoji na conversa: nada, pouco, médio ou muito?\n\n"
    "E você: como quer que eu te chame?"
)

Q_ABOUT = (
    "Boa, já tô tomando forma 🙂\n\n"
    "Agora me conta de você: no que você trabalha, o que curte fazer e o que "
    "costuma me pedir? Assim eu já te entendo melhor desde o começo."
)

Q_STYLE = (
    "Última coisa e te deixo em paz: como você prefere que eu responda no dia a "
    "dia? (ex.: curto e direto / com detalhe / passo a passo / sem enrolação)"
)

CLOSING = (
    "Fechou, agora a gente já se conhece 🙌\n\n"
    "Vou lembrar disso pra sempre — tenho memória persistente, então não precisa "
    "repetir. Sempre que algo mudar, é só me falar que eu atualizo seu perfil.\n\n"
    "Tô pronto 🚀 Qual é o próximo passo?"
)

IDENTITY_TEMPLATE = (
    "# IDENTITY.md\n\n"
    "A pessoa definiu quem eu sou. Devo seguir à risca em TODA conversa "
    "(nome, tipo de criatura, vibe e uso de emoji):\n\n"
    "{raw}\n\n"
    "Natureza: agente com memória persistente e workspace próprio desta pessoa.\n"
    "Regra de emoji: usar exatamente na medida pedida acima.\n\n"
    "> Identidade criada no onboarding em {date}.\n"
)


def _state_path(name: str):
    return ub.user_dir(name) / ".onboarding.json"


def _marker(name: str):
    return ub.user_dir(name) / ".onboarded"


def _load_state(name: str) -> dict:
    p = _state_path(name)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(name: str, data: dict) -> None:
    ub.ensure_user(name)
    _state_path(name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _clear_state(name: str) -> None:
    try:
        _state_path(name).unlink()
    except Exception:
        pass


def needs_onboarding(name: str) -> bool:
    return not _marker(name).exists()


def _write_identity(name: str, raw: str) -> None:
    ub.ensure_user(name)
    content = IDENTITY_TEMPLATE.format(raw=(raw or "").strip(), date=time.strftime("%Y-%m-%d %H:%M"))
    (ub.user_dir(name) / "IDENTITY.md").write_text(content, encoding="utf-8")


def _mark_done(name: str) -> None:
    try:
        _marker(name).write_text(time.strftime("%Y-%m-%d %H:%M:%S") + "\n", encoding="utf-8")
    except Exception:
        pass
    _clear_state(name)


def begin(name: str) -> list[str]:
    ub.ensure_user(name)
    _save_state(name, {"step": "identity"})
    return [WELCOME]


def handle(text: str, name: str) -> tuple[list[str], bool]:
    """Processa uma mensagem no fluxo de onboarding.

    Retorna (replies, done):
      - replies: mensagens que o bot deve enviar (pode ser vazio)
      - done:    True quando o onboarding acabou nesta chamada
    Se o usuário não está (nem entra) em onboarding, retorna ([], True) — o
    chamador segue o fluxo normal do bot.
    """
    low = (text or "").strip().lower()
    state = _load_state(name)
    active = bool(state)

    # Refazer a qualquer momento.
    if low in _RESTART_WORDS:
        return begin(name), False

    if not active:
        if needs_onboarding(name):
            return begin(name), False
        return [], True  # já passou pelo onboarding; fluxo normal

    # ---- no meio do fluxo ----
    if low in _SKIP_WORDS:
        _mark_done(name)
        return ["Tranquilo, deixamos pra depois 🙂 Qual é o próximo passo?"], True

    step = state.get("step") or "identity"

    if step == "identity":
        if not (text or "").strip():
            return [WELCOME], False
        _write_identity(name, text)
        # Se a pessoa disse como quer ser chamada, guardamos no perfil.
        apelido = _extrair_apelido(text)
        if apelido:
            ub.set_profile_field(name, "chamar", apelido)
        _save_state(name, {"step": "about"})
        return [Q_ABOUT], False

    if step == "about":
        about = (text or "").strip()
        if about:
            ub.set_profile_field(name, "trabalho", about)
            ub.remember(name, f"Onboarding — sobre a pessoa: {about}", kind="fact")
        _save_state(name, {"step": "style"})
        return [Q_STYLE], False

    if step == "style":
        estilo = (text or "").strip()
        if estilo:
            ub.set_profile_field(name, "estilo", estilo)
            ub.remember(name, f"Prefere respostas: {estilo}", kind="fact")
        _mark_done(name)
        return [CLOSING], True

    # Estado inesperado: encerra com elegância.
    _mark_done(name)
    return [CLOSING], True


def _extrair_apelido(text: str) -> Optional[str]:
    """Heurística leve: tenta pegar como a pessoa quer ser chamada."""
    m = None
    import re
    for pat in (r"me chama de ([A-Za-zÀ-ÿ0-9 ._-]{2,30})",
                r"pode me chamar de ([A-Za-zÀ-ÿ0-9 ._-]{2,30})",
                r"meu nome (?:é|e) ([A-Za-zÀ-ÿ0-9 ._-]{2,30})"):
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip(".!,")
    return None
