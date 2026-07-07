#!/usr/bin/env python3
"""
Demo end-to-end: simula o primeiro contato de dois usuários diferentes, roda o
onboarding completo, grava memória persistente/longo-prazo e mostra o contexto
por-usuário — provando que o bot conhece e responde adequadamente a cada um.

Roda sem LLM: o 'bot' aqui só monta o contexto e demonstra a personalização.
"""
from __future__ import annotations

import onboarding
import userbrain as ub


def conversa(name: str, respostas: list[str]) -> None:
    print(f"\n{'='*66}\n👤 PRIMEIRO CONTATO: {name}\n{'='*66}")
    replies, done = onboarding.handle("", name)   # dispara o onboarding
    for r in replies:
        print(f"🤖 {r}\n")
    for resp in respostas:
        print(f"👤 {resp}\n")
        replies, done = onboarding.handle(resp, name)
        for r in replies:
            print(f"🤖 {r}\n")
        if done:
            break


def mostrar_contexto(name: str) -> None:
    print(f"\n{'-'*66}\n🧠 CONTEXTO CARREGADO PARA {name} (vira system prompt)\n{'-'*66}")
    print(ub.context(name))


if __name__ == "__main__":
    import os
    import shutil
    # começa limpo pra demo ser reprodutível
    if ub.USERS_ROOT.exists():
        for n in ("Rafael", "Marina"):
            d = ub.user_dir(n)
            if d.exists():
                shutil.rmtree(d)

    conversa("Rafael", [
        "Te chamo de Nserver, é meu copiloto, vibe direta e técnica, emoji pouco. Pode me chamar de Rafa.",
        "Trabalho com automação e bots no Telegram, curto café e edição de vídeo. Costumo pedir deploy e debug.",
        "Curto e direto, sem enrolação.",
    ])

    conversa("Marina", [
        "Seu nome é Aurora, você é minha amiga assistente, vibe calorosa, emoji médio. Me chama de Mari.",
        "Sou nutricionista, gosto de corrida e leitura. Costumo pedir ajuda com textos e organização.",
        "Com detalhe e passo a passo, por favor.",
    ])

    # memória continua depois do onboarding
    ub.remember("Rafael", "Pediu pra priorizar o repo user-brain-kit hoje.", kind="daily")
    ub.remember("Marina", "Prefere ser lembrada de beber água.", kind="fact")

    # captura contínua: mensagens normais que revelam algo novo sobre a pessoa
    print(f"\n{'-'*66}\n📥 CAPTURA CONTÍNUA (mensagens normais, sem comando)\n{'-'*66}")
    for msg in [
        "aliás gosto de fotografia também",
        "agora trabalho com marketing digital",
        "moro em Fortaleza",
    ]:
        mudou = ub.observe("Rafael", msg)
        print(f"👤 {msg}\n   → capturado: {mudou or 'nada'}")

    mostrar_contexto("Rafael")
    mostrar_contexto("Marina")

    print(f"\n{'='*66}\n✅ Usuários no kit: {ub.list_users()}\n{'='*66}")
