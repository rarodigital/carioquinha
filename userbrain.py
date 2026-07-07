#!/usr/bin/env python3
"""
userbrain — cérebro por-usuário: perfil (USER.md) + memória persistente + memória
de longo prazo. Núcleo autônomo, sem dependência do nserver.

Espelhado no modelo do nserver (users/<slug>/agent-brain) e na camada "Cérebro
Pessoal" da Pixel (USER.md separado da identidade do agente + memória roteada em
daily / fatos duráveis). NÃO importa nem altera o nserver — é um repositório
próprio (futuro GitHub) que só reaproveita as boas ideias.

Estrutura em disco (tudo persistente — sobrevive a restart):

    data/users/<slug>/
    ├── USER.md                 # perfil estruturado da PESSOA (longo prazo)
    ├── IDENTITY.md             # persona do agente para esta pessoa
    ├── memory/
    │   ├── facts.md            # memória de LONGO PRAZO (fatos duráveis, sempre no contexto)
    │   └── {YYYY-MM-DD}.md     # daily notes (memória persistente do dia-a-dia)
    ├── .onboarding.json        # estado do onboarding em andamento
    └── .onboarded              # marcador de conclusão

Uso típico:

    import userbrain as ub
    ub.ensure_user("Rafael")
    ub.set_profile_field("Rafael", "chamar", "Rafa")
    ub.remember("Rafael", "Prefere respostas curtas e diretas.", kind="fact")
    ub.remember("Rafael", "Pediu ajuda com deploy do bot.", kind="daily")
    print(ub.context("Rafael"))   # bloco pronto pra virar system prompt do usuário
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

# ------------------------------------------------------------------ paths
# Raiz dos dados: ao lado deste arquivo por padrão; sobrescreve com USERBRAIN_DATA.
ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("USERBRAIN_DATA", ROOT / "data")).expanduser()
USERS_ROOT = DATA_ROOT / "users"

BRAIN_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")

# Campos canônicos do perfil da pessoa (ordem importa — vira a ordem no USER.md).
PROFILE_FIELDS = [
    ("chamar", "Como chamar"),
    ("nome_completo", "Nome completo"),
    ("trabalho", "Trabalho / o que faz"),
    ("interesses", "Interesses"),
    ("pedidos_comuns", "Pedidos comuns ao bot"),
    ("estilo", "Como gosta de ser tratado"),
    ("idioma", "Idioma"),
    ("fuso", "Fuso horário"),
]


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def user_slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "default")).strip("-")
    return s[:80] or "default"


def user_dir(name: str) -> Path:
    return USERS_ROOT / user_slug(name)


def memory_dir(name: str) -> Path:
    return user_dir(name) / "memory"


# ------------------------------------------------------------------ perfil
def _blank_user_md(name: str) -> str:
    linhas = ["# USER.md", "",
              f"Perfil da pessoa. Criado em {_now()}.",
              "Sempre carregado no contexto — é como o bot conhece e personaliza.",
              ""]
    for _key, label in PROFILE_FIELDS:
        # 'Como chamar' já entra com o nome conhecido; resto fica em branco.
        val = name if _key == "chamar" else ""
        linhas.append(f"- **{label}:** {val}")
    linhas.append("")
    return "\n".join(linhas)


def ensure_user(name: str) -> Path:
    """Garante a pasta e os arquivos-base do usuário. Idempotente."""
    d = user_dir(name)
    d.mkdir(parents=True, exist_ok=True)
    memory_dir(name).mkdir(parents=True, exist_ok=True)

    user_md = d / "USER.md"
    if not user_md.exists():
        user_md.write_text(_blank_user_md(name), encoding="utf-8")

    identity = d / "IDENTITY.md"
    if not identity.exists():
        identity.write_text(
            "# IDENTITY.md\n\n"
            "Persona do agente para esta pessoa (nome, natureza, vibe, emoji).\n"
            "Preenchido no onboarding.\n",
            encoding="utf-8",
        )

    facts = memory_dir(name) / "facts.md"
    if not facts.exists():
        facts.write_text(
            "# facts.md — memória de longo prazo\n\n"
            "Fatos duráveis sobre a pessoa. Sempre carregados no contexto.\n\n",
            encoding="utf-8",
        )
    return d


def read_profile_text(name: str) -> str:
    p = user_dir(name) / "USER.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def get_profile(name: str) -> dict:
    """Lê o USER.md e devolve os campos preenchidos como dict {key: valor}."""
    text = read_profile_text(name)
    label_to_key = {label.lower(): key for key, label in PROFILE_FIELDS}
    out: dict = {}
    for line in text.splitlines():
        m = re.match(r"^- \*\*(.+?):\*\*\s*(.*)$", line.strip())
        if not m:
            continue
        label, val = m.group(1).strip().lower(), m.group(2).strip()
        key = label_to_key.get(label)
        if key and val:
            out[key] = val
    return out


def set_profile_field(name: str, key: str, value: str) -> None:
    """Atualiza (ou preenche) um campo do USER.md preservando o resto."""
    ensure_user(name)
    valid = {k for k, _ in PROFILE_FIELDS}
    if key not in valid:
        raise ValueError(f"campo inválido: {key} (válidos: {sorted(valid)})")
    label = dict(PROFILE_FIELDS)[key]
    p = user_dir(name) / "USER.md"
    lines = p.read_text(encoding="utf-8").splitlines()
    pat = re.compile(rf"^- \*\*{re.escape(label)}:\*\*")
    novo = f"- **{label}:** {value.strip()}"
    for i, line in enumerate(lines):
        if pat.match(line.strip()):
            lines[i] = novo
            break
    else:
        lines.append(novo)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ memória
def remember(name: str, note: str, kind: str = "daily") -> Path:
    """Grava memória PERSISTENTE.

    kind="fact"  -> memória de LONGO PRAZO (memory/facts.md), sempre no contexto.
    kind="daily" -> daily note do dia (memory/{YYYY-MM-DD}.md), histórico persistente.
    """
    ensure_user(name)
    note = (note or "").strip()
    if not note:
        return memory_dir(name)

    if kind == "fact":
        target = memory_dir(name) / "facts.md"
        with target.open("a", encoding="utf-8") as f:
            f.write(f"- {note}\n")
        return target

    target = memory_dir(name) / f"{_today()}.md"
    header = f"# {_today()}\n\n"
    if not target.exists():
        target.write_text(header, encoding="utf-8")
    with target.open("a", encoding="utf-8") as f:
        f.write(f"- {time.strftime('%H:%M')} — {note}\n")
    return target


def long_term(name: str) -> str:
    p = memory_dir(name) / "facts.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def recent_daily(name: str, days: int = 2, max_chars: int = 4000) -> str:
    """Últimos N daily notes concatenados (memória persistente recente)."""
    d = memory_dir(name)
    if not d.exists():
        return ""
    files = sorted(
        (p for p in d.iterdir() if BRAIN_DATE_RE.match(p.name)),
        reverse=True,
    )[:days]
    chunks = [p.read_text(encoding="utf-8") for p in reversed(files)]
    text = "\n\n".join(chunks)
    return text[-max_chars:] if len(text) > max_chars else text


# ------------------------------------------------------------------ contexto
def context(name: str) -> str:
    """Monta o bloco de contexto por-usuário — pronto pra virar system prompt.

    É isto que faz o bot 'responder adequadamente a cada usuário': carrega o
    perfil (USER.md), a memória de longo prazo (facts.md) e o histórico recente.
    """
    ensure_user(name)
    partes = [
        "## Perfil do usuário (USER.md)",
        read_profile_text(name).strip(),
        "",
        "## Memória de longo prazo (facts.md)",
        long_term(name).strip(),
    ]
    recente = recent_daily(name).strip()
    if recente:
        partes += ["", "## Memória recente (daily notes)", recente]
    return "\n".join(partes).strip()


# ------------------------------------------------------------------ util
def list_users() -> list[str]:
    if not USERS_ROOT.exists():
        return []
    return sorted(p.name for p in USERS_ROOT.iterdir() if p.is_dir())


if __name__ == "__main__":
    # smoke test mínimo
    demo = "Exemplo"
    ensure_user(demo)
    set_profile_field(demo, "chamar", "Ex")
    remember(demo, "Gosta de café.", kind="fact")
    remember(demo, "Testou o userbrain.", kind="daily")
    print(context(demo))
