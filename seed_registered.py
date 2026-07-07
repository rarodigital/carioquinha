#!/usr/bin/env python3
"""
Semeia um USER.md (perfil vazio) para cada usuário JÁ CADASTRADO no nserver.

Lê os diretórios de usuário do nserver em modo SÓ-LEITURA — não abre, não altera
e não importa nenhum código do nserver. Apenas descobre os nomes e cria o cérebro
correspondente dentro do user-brain-kit (data/users/<slug>/).

Locais varridos (os que existirem):
  - <nserver>/nserver1/users/*/
  - <nserver>/users/*/
  - <nserver>/C:\\nserver1/users/*/   (pasta literal criada em ambiente Linux)

Sobrescreve? Não. Se o usuário já tem cérebro no kit, é pulado.
"""
from __future__ import annotations

import os
from pathlib import Path

import userbrain as ub

NSERVER = Path(os.environ.get("NSERVER_ROOT", "/root/nserverlbot")).expanduser()

CANDIDATOS = [
    NSERVER / "nserver1" / "users",
    NSERVER / "users",
    NSERVER / "C:\\nserver1" / "users",
]


def descobrir_usuarios() -> list[str]:
    nomes: set[str] = set()
    for base in CANDIDATOS:
        if not base.exists():
            continue
        for p in base.iterdir():
            if p.is_dir() and (p / "agent-brain").exists():
                nomes.add(p.name)
    return sorted(nomes)


def main() -> None:
    usuarios = descobrir_usuarios()
    if not usuarios:
        print("Nenhum usuário cadastrado encontrado no nserver.")
        return
    print(f"Usuários cadastrados no nserver: {usuarios}\n")
    for nome in usuarios:
        d = ub.user_dir(nome)
        ja_existia = (d / "USER.md").exists()
        ub.ensure_user(nome)
        status = "já existia (pulado)" if ja_existia else "USER.md criado"
        print(f"  • {nome:20s} → {status}  [{d}]")
    print(f"\nPronto. Usuários no kit: {ub.list_users()}")


if __name__ == "__main__":
    main()
