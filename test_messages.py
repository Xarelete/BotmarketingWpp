"""Teste de validação do gerador de mensagens anti-spam."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.message_generator import generate_unique_message

# Lead de teste
lead = {
    "name": "João Silva",
    "phone": "5511999887766",
}

# Campanha de teste
campaign = {
    "id": "camp_test123",
    "message_template_key": "reativacao_geral",
    "custom_data": {
        "empreendimento": "Residencial Aurora",
        "destaque": "Últimas 5 unidades com vista para o parque",
        "link": "https://imobiliaria.com/aurora",
        "preco": "A partir de R$ 450.000",
        "condicoes": "Entrada facilitada em até 60x",
    },
}

print("=" * 70)
print("🧪 TESTE: Geração de 5 mensagens únicas para o mesmo lead")
print("=" * 70)

messages = set()
for i in range(5):
    msg = generate_unique_message(lead, campaign)
    if msg:
        print(f"\n{'─' * 70}")
        print(f"📩 MENSAGEM {i+1}:")
        print(f"{'─' * 70}")
        print(msg)
        messages.add(msg)
    else:
        print(f"❌ Falha na tentativa {i+1}")

print(f"\n{'=' * 70}")
print(f"📊 RESULTADO: {len(messages)} mensagens únicas de {5} tentativas")
print(f"✅ Anti-repetição: {'FUNCIONANDO' if len(messages) == 5 else '⚠️ VERIFICAR'}")
print(f"{'=' * 70}")

# Teste lead sem nome
lead_sem_nome = {"name": "", "phone": "5521888776655"}
print(f"\n\n{'=' * 70}")
print("🧪 TESTE: Mensagem para lead SEM nome")
print(f"{'=' * 70}")
msg = generate_unique_message(lead_sem_nome, campaign)
if msg:
    print(msg)
    print("\n✅ Funciona sem nome!")

# Limpa arquivo de teste
try:
    os.remove(os.path.join("data", "dispatch_history.json"))
except:
    pass
