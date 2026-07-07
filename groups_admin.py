#!/usr/bin/env python3
"""
groups_admin — registrar / esquecer / listar grupos-projeto do carioquinha.

Um GRUPO do Telegram vira um PROJETO com memória e workspace próprios. Este
utilitário faz as duas pontas de uma vez:
  1) libera o grupo no acesso do Telegram (access.json) — quais grupos o bot ouve;
  2) rotula o grupo como projeto no carioquinha (identities.json).

USO (somente ADMIN — o guard confina o shell de não-admin, então só o admin
consegue rodar isto):

  python3 groups_admin.py register <group_id> <projeto> [--allow id1,id2] [--mention]
  python3 groups_admin.py forget   <projeto|group_id>
  python3 groups_admin.py list

Exemplos (uso conversacional pelo admin no chat: "libera o grupo -123 como projeto site"):
  python3 groups_admin.py register -5513505815 site-cliente
  python3 groups_admin.py forget site-cliente

Notas:
  - `--mention` exige que o bot seja mencionado no grupo (requireMention=true).
    Sem a flag, o grupo é marcado requireMention=false (mas lembre: se o modo
    privacidade do bot estiver LIGADO no BotFather, mencionar continua necessário).
  - `forget` remove a memória (data/users/<projeto>-grupo) e o workspace
    (workspaces/<projeto>) do disco, além das entradas em access.json e identities.json.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carioquinha as cq  # noqa: E402
import userbrain as ub    # noqa: E402

ACCESS = Path(os.environ.get("TELEGRAM_ACCESS", "/root/.claude/channels/telegram/access.json"))
IDENTITIES = cq.IDENTITIES


def _load(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_group_id(ident: dict, alvo: str) -> str | None:
    """Aceita group_id direto ou nome de projeto; devolve o group_id."""
    groups = ident.get("groups", {})
    if alvo in groups:
        return alvo
    for gid, cfg in groups.items():
        if (cfg or {}).get("project") == alvo:
            return gid
    return None


def register(group_id: str, project: str, allow: list[str], require_mention: bool) -> None:
    if not group_id.startswith("-"):
        print(f"ERRO: id de grupo deve começar com '-' (recebido: {group_id})")
        sys.exit(1)

    # 1) access.json — liberar o grupo (preserva o resto)
    access = _load(ACCESS, {"dmPolicy": "pairing", "allowFrom": [], "groups": {}, "pending": {}})
    if not allow:
        allow = list(access.get("allowFrom", []))  # herda quem já é liberado no DM
    access.setdefault("groups", {})[group_id] = {"requireMention": require_mention, "allowFrom": allow}
    _save(ACCESS, access)

    # 2) identities.json — rotular como projeto
    ident = _load(IDENTITIES, {"terminal_person": "admin", "admins": [], "people": {}})
    ident.setdefault("groups", {})[group_id] = {"project": project, "topic": ""}
    _save(IDENTITIES, ident)

    # 3) cria as pastas do projeto de cara
    ub.ensure_user(f"{project}-grupo")
    ws = cq.workspace_dir(project)
    print(f"✓ Grupo {group_id} registrado como projeto '{project}'.")
    print(f"  - acesso: liberado (requireMention={require_mention}, allowFrom={allow})")
    print(f"  - memoria: data/users/{project}-grupo/")
    print(f"  - workspace: {ws}")
    print("  Lembre: se o modo privacidade do bot estiver ON, mencione o bot no grupo.")


def forget(alvo: str) -> None:
    ident = _load(IDENTITIES, {})
    gid = _find_group_id(ident, alvo)
    # descobre o nome do projeto
    project = None
    if gid:
        project = (ident.get("groups", {}).get(gid) or {}).get("project")
    project = project or (alvo if not alvo.startswith("-") else f"grupo-{alvo.lstrip('-')}")

    removidos = []
    # remove memoria e workspace
    mem = ub.user_dir(f"{project}-grupo")
    if mem.exists():
        shutil.rmtree(mem, ignore_errors=True); removidos.append(str(mem))
    ws = cq.WORKSPACES_ROOT / ub.user_slug(project)
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True); removidos.append(str(ws))
    # remove das configs
    if gid:
        ident.get("groups", {}).pop(gid, None); _save(IDENTITIES, ident)
        access = _load(ACCESS, {})
        if access.get("groups", {}).pop(gid, None) is not None:
            _save(ACCESS, access)
        removidos.append(f"config do grupo {gid}")

    if removidos:
        print(f"✓ Projeto '{project}' esquecido. Removido:")
        for r in removidos:
            print(f"  - {r}")
    else:
        print(f"Nada encontrado para '{alvo}'.")


def listar() -> None:
    ident = _load(IDENTITIES, {})
    groups = ident.get("groups", {})
    if not groups:
        print("Nenhum grupo-projeto registrado.")
        return
    print("Grupos-projeto registrados:")
    for gid, cfg in groups.items():
        print(f"  - {gid} -> projeto '{(cfg or {}).get('project')}' (topic: {(cfg or {}).get('topic','')})")


def main(argv: list[str]) -> None:
    if not argv:
        print(__doc__); sys.exit(0)
    cmd = argv[0]
    if cmd == "register":
        if len(argv) < 3:
            print("uso: register <group_id> <projeto> [--allow id1,id2] [--mention]"); sys.exit(1)
        gid, project = argv[1], argv[2]
        allow: list[str] = []
        require_mention = "--mention" in argv
        if "--allow" in argv:
            i = argv.index("--allow")
            if i + 1 < len(argv):
                allow = [x.strip() for x in argv[i + 1].split(",") if x.strip()]
        register(gid, project, allow, require_mention)
    elif cmd == "forget":
        if len(argv) < 2:
            print("uso: forget <projeto|group_id>"); sys.exit(1)
        forget(argv[1])
    elif cmd == "list":
        listar()
    else:
        print(f"comando desconhecido: {cmd}"); print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
