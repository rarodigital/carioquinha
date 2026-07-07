#!/usr/bin/env python3
"""
Hook UserPromptSubmit — roda a cada mensagem que chega ao Claude Code.

1) Descobre o requester (pessoa/canal/papel) pela tag <channel> do harness.
2) Grava o estado ativo (usado pelo guard.py pra permissão).
3) Carrega a memória por-usuário (USER.md + fatos + daily) e injeta como contexto.
4) Captura fatos novos da mensagem (observe) — o perfil aprofunda sozinho.

Falha segura: qualquer erro NÃO deve travar o Claude Code; sai em silêncio.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import carioquinha as cq
    import userbrain as ub
except Exception:
    sys.exit(0)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    prompt = data.get("prompt") or data.get("user_prompt") or data.get("message") or ""
    session_id = data.get("session_id", "")

    channel, raw = cq.parse_prompt(prompt)
    info = cq.resolve(channel, raw)
    try:
        cq.set_active(info, session_id)
    except Exception:
        pass

    key = info["key"]
    try:
        ub.ensure_user(key)
        limpo = cq.strip_tags(prompt)
        if limpo:
            ub.observe(key, limpo)  # captura contínua
        contexto = ub.context(key)
    except Exception:
        contexto = ""

    nota = (f"[carioquinha] Falando com voce agora: **{info['person']}** "
            f"via {channel} (papel={info['role']}, memoria={key}).")
    if info["role"] != "admin":
        try:
            ws = cq.workspace_dir(info["person"])
        except Exception:
            ws = "(workspace)"
        # STAGING: copia anexos enviados (foto/arquivo) para dentro do workspace,
        # senao a jaula/leitura escopada nao enxerga (o inbox fica fora).
        staged = []
        try:
            staged = cq.stage_files(cq.parse_attachments(prompt), info["person"])
        except Exception:
            staged = []
        if staged:
            nota += f"\nARQUIVOS RECEBIDOS copiados para o workspace: {', '.join(staged)} (use-os de {ws})."
        nota += (
            f"\nESTE USUARIO E NAO-ADMIN. Workspace dele: {ws}"
            "\n- PODE: conversar, memoria propria, e editar/criar arquivos DENTRO do workspace "
            "(HTML, textos, arquivos que ele enviou). Salve tudo dentro dessa pasta e devolva pra ele."
            "\n- NAO PODE: editar fora do workspace, mexer na VPS/estrutura/sistema/nserver ou em "
            "arquivos de outros usuarios; e (por ora) nao pode rodar shell (Bash). "
            "Ferramentas que precisam de shell (editar foto, integracoes) ainda dependem do sandbox. "
            "Se ele pedir algo bloqueado, explique gentilmente."
        )
    else:
        nota += "\nAdmin: acesso total."

    out = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": nota + "\n\n" + (contexto or ""),
        }
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
