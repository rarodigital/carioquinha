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

    info = cq.resolve_prompt(prompt)
    channel = info["channel"]
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

    if info.get("scope") == "group":
        try:
            gws = cq.workspace_dir(info["person"])
        except Exception:
            gws = "(workspace)"
        nota = (f"[carioquinha] GRUPO/PROJETO: **{info['person']}** (papel de quem falou={info['role']}, "
                f"memoria compartilhada do grupo={key}). Trate deste projeto; mantenha TODOS os "
                f"arquivos do projeto em {gws}. A memoria e compartilhada por todos do grupo — o que "
                f"for definido aqui (assunto, decisoes) vale para o grupo.")
    else:
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
            "\n- PODE: conversar; memoria propria; ler/editar/criar arquivos DENTRO do workspace "
            "(HTML, textos, fotos, arquivos que ele enviou); e RODAR SHELL/FERRAMENTAS (Bash) — "
            "o shell dele roda automaticamente confinado numa jaula (sandbox) presa ao workspace, "
            "com rede liberada. Pode editar foto, rodar python, plugar integracoes etc. "
            "Salve tudo dentro do workspace e devolva pra ele."
            "\n- NAO PODE: ler/editar fora do workspace, mexer na VPS/estrutura/sistema/nserver ou "
            "em arquivos de outros usuarios (bloqueado por hook). Se ele pedir algo fora, explique "
            "gentilmente que so o admin faz isso; nao insista em caminhos fora do workspace."
        )
    else:
        nota += ("\nAdmin: acesso total. Para grupos-projeto (admin): "
                 "REGISTRAR um grupo -> `python3 /root/user-brain-kit/groups_admin.py register <group_id> <projeto>`; "
                 "ESQUECER/apagar um projeto -> `python3 /root/user-brain-kit/groups_admin.py forget <projeto>`. "
                 "Ex.: se o admin disser 'libera o grupo -123 como projeto site', rode o register.")

    # ONBOARDING: se a pessoa ainda nao formou a identidade do bot (sem .onboarded),
    # instrui o agente a conduzir um onboarding leve. Se ela adiar, o marcador
    # continua ausente e o lembrete volta nas proximas conversas (sem insistir).
    if info.get("scope") != "group":  # onboarding e por PESSOA, nao por grupo-projeto
        try:
            brain = ub.user_dir(key)
            onboarded = (brain / ".onboarded").exists()
        except Exception:
            brain, onboarded = None, True
        if not onboarded and brain is not None:
            nota += (
                "\n\n[ONBOARDING PENDENTE] Esta pessoa ainda nao concluiu o onboarding "
                f"(nao existe {brain}/.onboarded). Conduza um onboarding leve e acolhedor NESTA conversa, "
                "sem robotizar: (1) apresente-se em 1-2 linhas e diga que voce tem MEMORIA PERSISTENTE "
                "(vai lembrar dela); (2) pergunte como ela quer te chamar, que personalidade/vibe quer que "
                "voce tenha (direto, caloroso, tecnico, brincalhao...) e uso de emoji; (3) pergunte um pouco "
                "sobre ela (o que faz, o que costuma pedir). ADAPTE sua identidade ao que ela pedir. "
                f"Quando ela definir sua persona e como te chamar, PERSISTA: escreva {brain}/IDENTITY.md com "
                f"a persona escolhida e crie o arquivo {brain}/.onboarded (1 linha com a data) para concluir. "
                "Se ela NAO quiser agora, tudo bem: ajude no que pedir e NAO crie o .onboarded — voce lembrara "
                "de terminar de formar sua identidade nas proximas conversas. Toque no assunto de leve, sem insistir."
            )

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
