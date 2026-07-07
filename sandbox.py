#!/usr/bin/env python3
"""
sandbox — confina o shell de um NÃO-ADMIN ao próprio workspace usando bubblewrap.

A raiz inteira entra read-only (binários/libs funcionam), mas:
  - /root, /home, /opt, /tmp viram tmpfs (escondem segredos, nserver, outros
    usuários; qualquer escrita ali é efêmera e isolada);
  - só o workspace da pessoa é montado com ESCRITA real;
  - rede liberada (integrações/ferramentas), namespaces isolados.

Resultado: dentro da jaula ela faz tudo (editar foto, rodar ferramenta, instalar
libs no venv dela...), mas não consegue ler segredos nem alterar a VPS.

Testado com escapes reais (ver `python3 sandbox.py --selftest`).
"""
from __future__ import annotations

import shlex
from pathlib import Path

# Diretórios escondidos por tmpfs (nada real vaza; escrita ali é efêmera).
HIDE = ["/root", "/home", "/opt", "/tmp"]


def wrap_argv(command: str, workspace: str | Path) -> list[str]:
    ws = str(Path(workspace).resolve())
    argv = ["bwrap", "--ro-bind", "/", "/"]
    for d in HIDE:
        argv += ["--tmpfs", d]
    argv += [
        "--proc", "/proc", "--dev", "/dev",
        "--bind", ws, ws,
        "--chdir", ws,
        "--setenv", "HOME", ws,
        "--unshare-all", "--share-net",
        "--die-with-parent", "--new-session",
        "/usr/bin/bash", "-c", command,
    ]
    return argv


def wrap_command(command: str, workspace: str | Path) -> str:
    """Devolve UMA string de shell segura equivalente à jaula (pra virar Bash.command)."""
    return " ".join(shlex.quote(a) for a in wrap_argv(command, workspace))


def _selftest() -> int:
    import subprocess
    import tempfile
    ok = True
    ws = Path(tempfile.mkdtemp(prefix="sbx-"))
    alvo = Path("/root/.sandbox-selftest-vps.txt")
    alvo.write_text("original\n", encoding="utf-8")

    def run(cmd):
        return subprocess.run(wrap_argv(cmd, ws), capture_output=True, text=True)

    r = run("echo dentro > f.txt && cat f.txt")
    print("T1 escreve no ws:", "OK" if r.stdout.strip() == "dentro" else "FALHOU"); ok &= r.stdout.strip() == "dentro"

    run(f"echo HACK > {alvo}")
    intacto = alvo.read_text().strip() == "original"
    print("T2 nao altera VPS:", "OK" if intacto else "FALHOU"); ok &= intacto

    r = run("cat /root/.gh_token 2>/dev/null; echo fim")
    leak = "gh" in r.stdout and "fim" in r.stdout and len(r.stdout.strip()) > 5
    print("T3 nao le segredo:", "OK" if not leak else "FALHOU"); ok &= not leak

    r = run("python3 -c 'print(1+1)'")
    print("T4 ferramentas:", "OK" if r.stdout.strip() == "2" else "FALHOU"); ok &= r.stdout.strip() == "2"

    alvo.unlink(missing_ok=True)
    import shutil; shutil.rmtree(ws, ignore_errors=True)
    print("RESULTADO:", "TUDO OK ✅" if ok else "FALHA ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    # uso: sandbox.py <workspace> <comando...>
    if len(sys.argv) >= 3:
        print(wrap_command(sys.argv[2], sys.argv[1]))
