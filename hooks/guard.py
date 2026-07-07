#!/usr/bin/env python3
"""
Hook PreToolUse — guardrail de permissão por-usuário.

Bloqueia ações sensíveis (shell, edição de arquivo, git, mudanças na VPS) quando
quem está falando NÃO é admin. Admin (Adalto, no terminal ou no Telegram nydollar)
passa livre. O requester atual vem do estado gravado pelo on_prompt.py.

Retorno:
  - admin  -> exit 0 (sem decisão; segue as regras normais de permissão)
  - normal + ferramenta sensível -> permissionDecision: "deny"
  - normal + ferramenta neutra    -> exit 0

Falha segura para o TERMINAL: se não houver estado, assume admin (a máquina é do
Adalto). Todo turno de Telegram sobrescreve o estado, então não-admin nunca herda
admin numa conversa real.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Ferramentas que podem alterar o sistema/estrutura — barradas para não-admin.
SENSIVEIS = {"Bash", "Edit", "Write", "NotebookEdit", "MultiEdit"}


def _allow() -> None:
    sys.exit(0)


def _deny(pessoa: str, tool: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Usuario '{pessoa}' e nao-admin: a acao '{tool}' (shell/arquivo/VPS) "
                f"esta bloqueada. So o admin (Adalto) pode alterar a estrutura. "
                f"Responda ao usuario sem executar essa acao."
            ),
        }
    }
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        _allow()
    tool = data.get("tool_name", "")

    try:
        import carioquinha as cq
        active = cq.get_active()
    except Exception:
        _allow()  # sem como resolver -> não trava o admin no terminal

    if active.get("role") == "admin":
        _allow()
    if tool in SENSIVEIS:
        _deny(active.get("person", "desconhecido"), tool)
    _allow()


if __name__ == "__main__":
    main()
