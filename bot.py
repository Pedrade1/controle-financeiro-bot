from openai import OpenAI
import pandas as pd
from datetime import datetime
import json
import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================
# CONFIG (RENDER + SEGURO)
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

if not TELEGRAM_TOKEN or not OPENAI_KEY:
    print("⚠️ Variáveis não encontradas (Render Environment)")

client = OpenAI(api_key=OPENAI_KEY)

usuarios = {}

# =========================
# SERVIDOR FAKE (RENDER FREE)
# =========================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot rodando')

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()

threading.Thread(target=run_server, daemon=True).start()

# =========================
# PARSER LOCAL (ECONOMIA)
# =========================
def parse_local(texto):
    match = re.search(r'(\d+[.,]?\d*)', texto)
    if not match:
        return None

    valor = float(match.group(1).replace(",", "."))
    texto_lower = texto.lower()

    categorias = {
    # 🚗 TRANSPORTE
    "uber": "transporte",
    "99": "transporte",
    "taxi": "transporte",
    "ônibus": "transporte",
    "onibus": "transporte",
    "bus": "transporte",
    "metro": "transporte",
    "trem": "transporte",
    "passagem": "transporte",

    # ⛽ COMBUSTÍVEL
    "gasolina": "combustivel",
    "etanol": "combustivel",
    "diesel": "combustivel",
    "posto": "combustivel",
    "combustivel": "combustivel",

    # 🛒 MERCADO
    "mercado": "mercado",
    "supermercado": "mercado",
    "compras": "mercado",
    "feira": "mercado",
    "hortifruti": "mercado",

    # 🍔 COMIDA
    "ifood": "comida",
    "lanche": "comida",
    "restaurante": "comida",
    "jantar": "comida",
    "almoço": "comida",
    "almoco": "comida",
    "pizza": "comida",
    "hamburguer": "comida",
    "hambúrguer": "comida",
    "comida": "comida",
    "rodizio de pizza": "comida",
    "rodizio japones": "comida",
    

    # 💊 SAÚDE
    "farmacia": "saude",
    "remedio": "saude",
    "remédio": "saude",
    "medico": "saude",
    "consulta": "saude",
    "exame": "saude",
    "skincare": "saude",
    "esmalte": "saude",
    "algodão": "saude",
    "algodao": "saude",
    "lixa de unha": "saude",
    

    # 👕 ROUPAS
    "tenis": "roupas",
    "tênis": "roupas",
    "blusa": "roupas",
    "camisa": "roupas",
    "camiseta": "roupas",
    "short": "roupas",
    "bermuda": "roupas",
    "calça": "roupas",
    "calca": "roupas",
    "meia": "roupas",
    "cueca": "roupas",
    "calcinha": "roupas",
    "vestido": "roupas",
    "jaqueta": "roupas",
    "casaco": "roupas",
    "roupa": "roupas",
    "roupas": "roupas",
    "regata": "roupa",
    "regatas": "roupa",
    
    
    }

    for palavra, cat in categorias.items():
        if palavra in texto_lower:
            return [{
                "valor": valor,
                "categoria": cat,
                "descricao": texto
            }]

    return None

# =========================
# FUNÇÕES (MELHORADAS)
# =========================
def carregar_df():
    if not os.path.exists("gastos.csv"):
        return pd.DataFrame(columns=["user", "valor", "categoria", "descricao", "data"])
    return pd.read_csv("gastos.csv")


def salvar_gasto(dados, user):
    df = carregar_df()

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


def resumo_mes(user):
    df = carregar_df()
    df = df[df["user"] == user]

    if df.empty:
        return None

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    hoje = datetime.now()

    df = df[(df["data"].dt.month == hoje.month) & (df["data"].dt.year == hoje.year)]

    if df.empty:
        return None

    return df.groupby("categoria")["valor"].sum(), df["valor"].sum()


# =========================
# TELEGRAM
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    texto_lower = texto.lower()
    telegram_id = str(update.message.from_user.id)

    if texto_lower in ["/start", "ajuda"]:
        await update.message.reply_text(
            "🦆 *Tio Patinhas BOT* 💰\n\n"
            "Envie gastos como:\n"
            "_ifood 30, uber 20_\n\n"
            "Comandos:\n"
            "• resumo\n"
            "• planilha\n"
            "• dividir\n"
            "• trocar\n",
            parse_mode="Markdown"
        )
        return

    if "trocar" in texto_lower:
        usuarios.pop(telegram_id, None)
        await update.message.reply_text("1 - Henrique\n2 - Dona Onça 🐆")
        return

    if telegram_id not in usuarios:
        if texto_lower in ["1", "henrique"]:
            usuarios[telegram_id] = "Henrique"
        elif texto_lower in ["2", "dona onça", "dona onca"]:
            usuarios[telegram_id] = "Dona Onça 🐆"
        else:
            await update.message.reply_text("1 - Henrique\n2 - Dona Onça 🐆")
            return

    user = usuarios[telegram_id]

    if "resumo" in texto_lower:
        dados = resumo_mes(user)
        if not dados:
            await update.message.reply_text("🦆 Sem gastos no mês.")
            return

        agrupado, total = dados
        msg = f"🦆 {user}\n\n"

        for cat, val in agrupado.items():
            msg += f"{cat}: R${val:.2f}\n"

        msg += f"\nTotal: R${total:.2f}"
        await update.message.reply_text(msg)
        return

    # =========================
    # REGISTRO DE GASTO
    # =========================
    try:
        dividir = "dividir" in texto_lower

        dados = parse_local(texto)

        # 🔥 só usa OpenAI se não conseguir localmente
        if not dados:
            resposta = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=40,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": f"Extraia JSON com valor, categoria e descricao de: {texto}"
                }]
            )

            conteudo = resposta.choices[0].message.content.strip()
            conteudo = conteudo.replace("```json", "").replace("```", "")
            dados = json.loads(conteudo)

            if isinstance(dados, dict):
                dados = [dados]

        msg = f"🦆 {user}:\n"

        for g in dados:
            valor = float(g["valor"])

            if dividir:
                metade = valor / 2
                salvar_gasto({**g, "valor": metade}, user)

                outro = "Dona Onça 🐆" if user == "Henrique" else "Henrique"
                salvar_gasto({**g, "valor": metade}, outro)

                msg += f"\n🤝 Dividido: R${metade:.2f} cada\n"
            else:
                salvar_gasto(g, user)
                msg += f"\n✅ {g['categoria']} - R${valor:.2f}\n"

        await update.message.reply_text(msg)

    except Exception as e:
        print("Erro:", e)
        await update.message.reply_text("🦆 Tenta algo como: mercado 50")


# =========================
# INICIAR
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, responder))

print("🤖 Bot rodando...")
app.run_polling()