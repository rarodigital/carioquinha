#!/usr/bin/env python3
"""
carioquinha — camada de identidade + roteamento sobre o userbrain.

Resolve QUEM está falando (pessoa, canal, papel) e qual é a CHAVE de memória
`<pessoa>-<canal>`, de modo que Telegram, Web e Terminal fiquem SEPARADOS por
padrão (mesmo repositório de memórias, cérebros distintos). Usado pelos hooks
do Claude Code:

  - hooks/on_prompt.py  (UserPromptSubmit): descobre o requester, grava o estado
    ativo, carrega a memória da pessoa e captura fatos novos.
  - hooks/guard.py      (PreToolUse): bloqueia ações sensíveis para não-admin.

Papéis:
  admin  → tudo, inclusive shell/arquivos/git/VPS (Adalto).
  normal → chat + memória própria + criativo; ações sensíveis bloqueadas.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import userbrain as ub

ROOT = Path(__file__).resolve().parent
IDENTITIES = ROOT / "identities.json"
STATE = ub.DATA_ROOT / ".active-requester.json"

_CHANNEL_TAG = re.compile(r"<channel\b[^>]*>", re.IGNORECASE)
_ATTR = lambda name, tag: (re.search(rf'{name}="([^"]*)"', tag) or [None, ""])[1] \
    if re.search(rf'{name}="([^"]*)"', tag) else ""


def load_identities() -> dict:
    try:
        return json.loads(IDENTITIES.read_text(encoding="utf-8"))
    except Exception:
        return {"terminal_person": "admin", "admins": [], "people": {}}


def parse_prompt(prompt: str) -> tuple[str, str]:
    """Extrai (canal, id_bruto) da tag <channel ...> do harness. Sem tag = terminal."""
    m = _CHANNEL_TAG.search(prompt or "")
    if not m:
        return ("terminal", "")
    tag = m.group(0)
    source = _ATTR("source", tag) or "terminal"
    # Telegram: preferir chat_id (numérico e estável); cair pra user.
    raw = ""
    if source.lower() == "telegram":
        raw = _ATTR("chat_id", tag) or _ATTR("user", tag)
    else:
        raw = _ATTR("user", tag) or _ATTR("chat_id", tag)
    return (source.lower(), (raw or "").strip())


def strip_tags(text: str) -> str:
    return _CHANNEL_TAG.sub("", text or "").strip()


def resolve(channel: str, raw_user: str) -> dict:
    ident = load_identities()
    channel = (channel or "terminal").lower()
    raw = str(raw_user or "").strip()

    if channel == "terminal":
        person = ident.get("terminal_person", "admin")
        return {"channel": "terminal", "raw": raw, "person": person,
                "role": "admin", "key": f"{person}-terminal"}

    person = ident.get("people", {}).get(raw) or f"{channel[:2]}-{raw or 'anon'}"
    role = "admin" if raw in ident.get("admins", []) else "normal"
    return {"channel": channel, "raw": raw, "person": person,
            "role": role, "key": f"{person}-{channel}"}


def set_active(info: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")


def get_active() -> dict:
    """Estado do requester atual. Default = terminal/admin (a máquina é do Adalto)."""
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"channel": "terminal", "raw": "", "person": "adalto",
                "role": "admin", "key": "adalto-terminal"}


if __name__ == "__main__":
    # teste rápido do resolvedor
    exemplos = [
        ("terminal", ""),
        ("telegram", "7403271687"),
        ("telegram", "207597739"),
        ("telegram", "999888"),
        ("web", "rafaela"),
    ]
    for ch, u in exemplos:
        print(f"{ch:9s} {u:12s} -> {resolve(ch, u)}")
    print("\nparse:", parse_prompt('<channel source="telegram" chat_id="7403271687" user="nydollar">oi'))
