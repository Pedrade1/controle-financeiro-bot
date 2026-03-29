from openai import OpenAI
import pandas as pd
from datetime import datetime
import json
import os

# =========================
# CONFIG (SEGURO)
# =========================
OPENAI_KEY = os.getenv("OPENAI_KEY")

if not OPENAI_KEY:
    raise ValueError("⚠️ Defina OPENAI_KEY no PowerShell antes de rodar.")

client = OpenAI(api_key=OPENAI_KEY)

CONFIG_FILE = "config.json"


# =========================
# MEMÓRIA DO USUÁRIO
# =========================
def carregar_usuario():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return config.get("user")

    user_input = input("Quem está usando? (1 = Henrique / 2 = Dona Onça): ")

    if user_input == "1":
        user = "Henrique"
    else:
        user = "Dona Onça"

    with open(CONFIG_FILE, "w") as f:
        json.dump({"user": user}, f)

    return user


def trocar_usuario():
    user_input = input("Trocar para quem? (1 = Henrique / 2 = Dona Onça): ")

    if user_input == "1":
        user = "Henrique"
    else:
        user = "Dona Onça"

    with open(CONFIG_FILE, "w") as f:
        json.dump({"user": user}, f)

    return user


user = carregar_usuario()


# =========================
# FUNÇÕES
# =========================
def salvar_gasto(dados, user):
    try:
        df = pd.read_csv("gastos.csv")
    except:
        df = pd.DataFrame(columns=["user", "valor", "categoria", "descricao", "data"])

    try:
        valor = float(dados["valor"])
    except:
        return

    novo = {
        "user": user,
        "valor": valor,
        "categoria": dados["categoria"],
        "descricao": dados["descricao"],
        "data": datetime.now().strftime("%Y-%m-%d")
    }

    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
    df.to_csv("gastos.csv", index=False)


def total_categoria_mes(categoria, user):
    try:
        df = pd.read_csv("gastos.csv")
    except:
        return 0

    df = df[df["user"] == user]

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    hoje = datetime.now()
    inicio_mes = hoje.replace(day=1)

    mes = df[df["data"] >= inicio_mes]
    total = mes[mes["categoria"] == categoria]["valor"].sum()

    return total


def resumo(user):
    try:
        df = pd.read_csv("gastos.csv")
    except:
        return "🦆 Tio Patinhas:\nNenhum gasto ainda."

    df = df[df["user"] == user]

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    hoje = datetime.now()
    inicio_mes = hoje.replace(day=1)

    mes = df[df["data"] >= inicio_mes]

    if mes.empty:
        return f"\n🦆 Tio Patinhas ({user}):\nNenhum gasto no mês ainda."

    resumo = mes.groupby("categoria")["valor"].sum()

    texto = f"\n🦆 Tio Patinhas ({user}):\n"
    texto += "\n📊 RESUMO DO MÊS:\n\n"

    for cat, val in resumo.items():
        texto += f"{cat}: R${val:.2f}\n"

    texto += f"\n💰 TOTAL: R${mes['valor'].sum():.2f}"

    return texto


# =========================
# LOOP PRINCIPAL
# =========================
while True:
    texto = input("Fala ai com o que tu gastou: ")

    texto_lower = texto.lower()

    if "resumo" in texto_lower:
        print(resumo(user))
        continue

    if "trocar" in texto_lower:
        user = trocar_usuario()
        print(f"\n🦆 Tio Patinhas:\nAgora você é {user}\n")
        continue

    if "usuario" in texto_lower:
        print(f"\n🦆 Tio Patinhas:\nVocê é {user}\n")
        continue

    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": f"""
Leia o gasto abaixo e extraia:

- valor (apenas número)
- descrição curta
- categoria (escolha apenas UMA):

CATEGORIAS:
- transporte
- combustivel
- mercado
- comida
- saude

REGRAS:
- limpeza → mercado
- comida fora → comida
- rodizios, comida japonesa, sushi → comida 
- gasolina → combustivel
- NÃO inventar categoria

Retorne JSON válido:

[
  {{
    "valor": numero,
    "descricao": "texto",
    "categoria": "texto"
  }}
]

GASTO: {texto}
"""
            }
        ]
    )

    conteudo = resposta.choices[0].message.content.strip()
    conteudo = conteudo.replace("```json", "").replace("```", "").strip()

    try:
        dados = json.loads(conteudo)

        if not dados:
            print("🦆 Tio Patinhas:\nNenhum gasto identificado.")
            continue

        if isinstance(dados, dict):
            dados = [dados]

        mensagem = f"\n🦆 Tio Patinhas ({user}):\n"

        for gasto in dados:
            try:
                valor = float(gasto["valor"])
            except:
                continue

            if valor == 0:
                continue

            salvar_gasto(gasto, user)
            total = total_categoria_mes(gasto["categoria"], user)

            mensagem += f"\n✅ {gasto['categoria']} - R${valor:.2f}"
            mensagem += f"\n📊 Total no mês: R${total:.2f}\n"

        print(mensagem)

    except Exception as e:
        print("Erro:", e)
