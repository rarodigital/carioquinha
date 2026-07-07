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

    channel, raw = cq.parse_prompt(prompt)
    info = cq.resolve(channel, raw)
    try:
        cq.set_active(info)
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
        nota += ("\nESTE USUARIO E NAO-ADMIN: pode conversar, usar a propria memoria e "
                 "ferramentas criativas. Acoes de shell, edicao de arquivos, git/GitHub, "
                 "deploy e qualquer mudanca na VPS/estrutura estao BLOQUEADAS por hook. "
                 "Nao tente executa-las; se ele pedir, explique gentilmente que so o admin faz isso.")
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
