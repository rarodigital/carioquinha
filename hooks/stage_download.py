#!/usr/bin/env python3
"""
Hook PostToolUse — staging de anexos baixados (ex.: download_attachment do Telegram).

Quando o agente baixa um arquivo (que costuma cair no inbox, FORA do workspace),
este hook copia o arquivo para o workspace do NÃO-ADMIN atual e avisa o agente
do novo caminho — assim a leitura escopada e a jaula conseguem enxergar.

Admin: não faz nada (tem acesso total). Falha segura: nunca trava o turno.
"""
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_PATH_RE = re.compile(r"/[\w.\-/ ]+\.[A-Za-z0-9]{1,8}")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    session_id = data.get("session_id", "")
    try:
        import carioquinha as cq
        active = cq.get_active(session_id)
    except Exception:
        sys.exit(0)

    if active.get("role") == "admin":
        sys.exit(0)  # admin não precisa de staging

    person = active.get("person", "")
    try:
        ws = cq.workspace_dir(person).resolve()
    except Exception:
        sys.exit(0)

    # procura caminhos de arquivo existentes na resposta da ferramenta
    blob = json.dumps(data.get("tool_response", ""), ensure_ascii=False)
    candidatos = []
    for m in _PATH_RE.findall(blob):
        p = Path(m.strip())
        try:
            if p.is_file() and ws not in p.resolve().parents:
                candidatos.append(p)
        except Exception:
            pass

    staged = []
    for p in candidatos:
        try:
            dest = ws / p.name
            shutil.copy2(p, dest)
            staged.append(dest.name)
        except Exception:
            pass

    if staged:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[carioquinha] Anexo(s) copiado(s) para o workspace de {person}: "
                    f"{', '.join(staged)} (em {ws}). Trabalhe a partir dai."
                ),
            }
        }, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
