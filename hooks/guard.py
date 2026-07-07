#!/usr/bin/env python3
"""
Hook PreToolUse — guardrail de permissão por-usuário, com escopo por CAMINHO.

Modelo:
  admin (Adalto)  -> acesso total (terminal e Telegram nydollar).
  normal (demais) -> LIBERDADE TOTAL dentro do próprio workspace
                     (editar arquivos que enviou, HTML, etc.), mas BLOQUEIO
                     fora dele (VPS/estrutura/sistema/outros usuários).

Regras para NÃO-ADMIN:
  - Edit/Write/NotebookEdit/MultiEdit: permitido SE o arquivo estiver dentro do
    workspace da pessoa; senão negado.
  - Bash: negado por enquanto (confinamento seguro de shell exige sandbox de SO;
    ver README / decisão pendente).

O requester atual vem do estado por-sessão gravado pelo on_prompt.py.
Falha segura para o TERMINAL: sem estado -> assume admin (a máquina é do Adalto).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FILE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
SHELL_TOOLS = {"Bash"}


def _allow() -> None:
    sys.exit(0)


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


def _target_paths(tool_input: dict) -> list[str]:
    out = []
    for k in ("file_path", "notebook_path", "path"):
        v = tool_input.get(k)
        if isinstance(v, str) and v:
            out.append(v)
    # MultiEdit e afins podem trazer lista de edits com file_path repetido no topo
    return out


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        _allow()

    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    session_id = data.get("session_id", "")

    try:
        import carioquinha as cq
        active = cq.get_active(session_id)
    except Exception:
        _allow()  # sem como resolver -> não trava o admin no terminal

    if active.get("role") == "admin":
        _allow()

    person = active.get("person", "desconhecido")

    # ---- NÃO-ADMIN ----
    if tool in FILE_TOOLS:
        try:
            import carioquinha as cq
            ws = cq.workspace_dir(person).resolve()
        except Exception:
            _deny(f"Nao consegui resolver o workspace de '{person}'. Acao '{tool}' bloqueada por seguranca.")
        alvos = _target_paths(tool_input)
        if not alvos:
            _deny(f"Acao '{tool}' sem caminho claro; bloqueada para nao-admin '{person}'.")
        for p in alvos:
            try:
                dest = Path(p).resolve()
            except Exception:
                _deny(f"Caminho invalido '{p}'. Bloqueado.")
            if ws != dest and ws not in dest.parents:
                _deny(
                    f"Usuario '{person}' (nao-admin) so pode editar dentro do proprio workspace "
                    f"({ws}). O caminho '{dest}' esta FORA (VPS/estrutura) e foi bloqueado. "
                    f"Escreva o arquivo dentro do workspace da pessoa e responda a ela."
                )
        _allow()  # todos os alvos dentro do workspace

    if tool in SHELL_TOOLS:
        _deny(
            f"Usuario '{person}' (nao-admin) ainda nao pode rodar shell (Bash). "
            f"Edicoes de arquivo no workspace dele funcionam normalmente. "
            f"Ferramentas que precisam de shell (foto/integracoes) dependem do sandbox "
            f"de SO, que ainda nao esta ativo. Responda sem executar shell."
        )

    _allow()  # ferramentas neutras (Read, etc.) liberadas


if __name__ == "__main__":
    main()
