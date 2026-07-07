#!/usr/bin/env python3
"""
Hook PreToolUse — guardrail de permissão por-usuário, com escopo por CAMINHO.

Modelo:
  admin (Adalto)  -> acesso total (terminal e Telegram nydollar).
  normal (demais) -> LIBERDADE TOTAL dentro do próprio workspace
                     (editar arquivos que enviou, HTML, etc.), mas BLOQUEIO
                     fora dele (VPS/estrutura/sistema/outros usuários).

Regras para NÃO-ADMIN:
  - Read/Glob/Grep e Edit/Write/NotebookEdit/MultiEdit: permitido SE o caminho
    estiver dentro do workspace da pessoa; senão negado.
  - Bash: NÃO é negado — o comando é embrulhado numa jaula bubblewrap (sandbox.py)
    confinada ao workspace e liberado via `updatedInput`.

O requester atual vem do estado por-sessão gravado pelo on_prompt.py.
Falha segura para o TERMINAL: sem estado -> assume admin (a máquina é do Adalto).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FILE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
READ_TOOLS = {"Read", "Glob", "Grep"}
PATH_SCOPED = FILE_TOOLS | READ_TOOLS
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
    if tool in PATH_SCOPED:
        acao = "ler" if tool in READ_TOOLS else "editar"
        try:
            import carioquinha as cq
            import userbrain as ub
            ws = cq.workspace_dir(person).resolve()
            brain = ub.user_dir(active.get("key", "")).resolve()  # memória PRÓPRIA da pessoa
        except Exception:
            _deny(f"Nao consegui resolver o workspace de '{person}'. Acao '{tool}' bloqueada por seguranca.")
        roots = [ws, brain]  # pode mexer no proprio workspace e na propria memoria; nada alem
        alvos = _target_paths(tool_input)
        if not alvos:
            _deny(f"Acao '{tool}' sem caminho claro; bloqueada para nao-admin '{person}' (so dentro do workspace/memoria dele).")
        for p in alvos:
            try:
                dest = Path(p).resolve()
            except Exception:
                _deny(f"Caminho invalido '{p}'. Bloqueado.")
            if not any(r == dest or r in dest.parents for r in roots):
                _deny(
                    f"Usuario '{person}' (nao-admin) so pode {acao} no proprio workspace ({ws}) ou "
                    f"na propria memoria ({brain}). O caminho '{dest}' esta FORA (VPS/estrutura/outros "
                    f"usuarios) e foi bloqueado. Trabalhe dentro do espaco da pessoa e responda a ela."
                )
        _allow()  # todos os alvos dentro do workspace/memória da própria pessoa

    if tool in SHELL_TOOLS:
        # Bash de nao-admin: NAO nega — embrulha na jaula (bwrap) confinada ao
        # workspace e libera. Ela roda ferramentas/integracoes sem alcancar a VPS.
        cmd = tool_input.get("command", "")
        if not cmd:
            _allow()
        try:
            import carioquinha as cq
            import sandbox
            ws = cq.workspace_dir(person)
            wrapped = sandbox.wrap_command(cmd, ws)
        except Exception as e:
            _deny(f"Nao consegui confinar o shell de '{person}' com seguranca ({e}). Acao bloqueada.")
        novo = dict(tool_input)
        novo["command"] = wrapped
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"Shell de '{person}' confinado ao workspace (sandbox).",
                "updatedInput": novo,
            }
        }, ensure_ascii=False))
        sys.exit(0)

    _allow()  # ferramentas neutras (Read, etc.) liberadas


if __name__ == "__main__":
    main()
