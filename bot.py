from openai import OpenAI
import pandas as pd
from datetime import datetime
import json
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================
# CONFIG (SEGURO)
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_KEY")

if not TELEGRAM_TOKEN or not OPENAI_KEY:
    raise ValueError("⚠️ Defina TELEGRAM_TOKEN e OPENAI_KEY no PowerShell antes de rodar.")

client = OpenAI(api_key=OPENAI_KEY)

usuarios = {}

# =========================
# FUNÇÕES
# =========================
def carregar_df():
    try:
        return pd.read_csv("gastos.csv")
    except:
        return pd.DataFrame(columns=["user", "valor", "categoria", "descricao", "data"])


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


def total_categoria_mes(user, categoria):
    df = carregar_df()
    df = df[df["user"] == user]

    if df.empty:
        return 0

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    hoje = datetime.now()

    df_mes = df[
        (df["data"].dt.month == hoje.month) &
        (df["data"].dt.year == hoje.year)
    ]

    df_cat = df_mes[df_mes["categoria"] == categoria]

    return df_cat["valor"].sum()


def resumo_mes(user):
    df = carregar_df()
    df = df[df["user"] == user]

    if df.empty:
        return None

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    hoje = datetime.now()

    df_mes = df[
        (df["data"].dt.month == hoje.month) &
        (df["data"].dt.year == hoje.year)
    ]

    if df_mes.empty:
        return None

    agrupado = df_mes.groupby("categoria")["valor"].sum()
    total = df_mes["valor"].sum()

    return agrupado, total


def resumo_anual(user):
    df = carregar_df()
    df = df[df["user"] == user]

    if df.empty:
        return None

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    ano = datetime.now().year

    df_ano = df[df["data"].dt.year == ano]

    if df_ano.empty:
        return None

    agrupado = df_ano.groupby("categoria")["valor"].sum()
    total = df_ano["valor"].sum()

    return agrupado, total


def gerar_planilha_profissional(user):
    df = carregar_df()
    df = df[df["user"] == user]

    if df.empty:
        return None

    df["data"] = pd.to_datetime(df["data"], errors="coerce")

    hoje = datetime.now()
    df_mes = df[
        (df["data"].dt.month == hoje.month) &
        (df["data"].dt.year == hoje.year)
    ]

    nome = f"gastos_{user}.xlsx"

    with pd.ExcelWriter(nome, engine="openpyxl") as writer:
        df_mes.to_excel(writer, sheet_name="Dados", index=False)

        resumo = df_mes.groupby("categoria")["valor"].sum().reset_index()
        resumo.to_excel(writer, sheet_name="Resumo", index=False)

        from openpyxl.chart import PieChart, Reference

        worksheet = writer.sheets["Resumo"]

        chart = PieChart()
        data = Reference(worksheet, min_col=2, min_row=1, max_row=len(resumo)+1)
        labels = Reference(worksheet, min_col=1, min_row=2, max_row=len(resumo)+1)

        chart.add_data(data, titles_from_data=True)
        chart.set_categories(labels)
        chart.title = "Gastos por Categoria"

        worksheet.add_chart(chart, "E2")

    return nome


def mensagem_inicio():
    return (
        "🦆 *Tio Patinhas BOT* 💰\n\n"
        "Controle seus gastos de forma inteligente, tmj sempre:\n\n"
        "📥 Envie qualquer gasto:\n"
        "_ex: ifood 30, uber 20, mercado 100 ou docinho 20_\n\n"
        "📊 *Comandos disponíveis:*\n"
        "• resumo → ver gastos do mês\n"
        "• anual → resumo do ano\n"
        "• planilha → gerar Excel completo\n"
        "• dividir → dividir gastos( Ex: Pizza 40 dividir)\n"
        "• trocar → mudar usuário\n"
    )


# =========================
# TELEGRAM
# =========================
async def responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    texto_lower = texto.lower()
    telegram_id = str(update.message.from_user.id)

    if texto_lower in ["/start", "ajuda"]:
        await update.message.reply_text(mensagem_inicio(), parse_mode="Markdown")
        return

    if "trocar" in texto_lower:
        usuarios.pop(telegram_id, None)
        await update.message.reply_text(
            "🦆 Quem está usando?\n\n1 - Henrique\n2 - Dona Onça 🐆"
        )
        return

    if telegram_id not in usuarios:
        if texto_lower in ["1", "henrique"]:
            usuarios[telegram_id] = "Henrique"
            await update.message.reply_text("🦆 Henrique selecionado 💰\n\n" + mensagem_inicio(), parse_mode="Markdown")
            return

        elif texto_lower in ["2", "dona onça", "dona onca"]:
            usuarios[telegram_id] = "Dona Onça 🐆"
            await update.message.reply_text("🦆 Dona Onça 🐆 selecionada 💰\n\n" + mensagem_inicio(), parse_mode="Markdown")
            return

        else:
            await update.message.reply_text(
                "🦆 Quem está usando?\n\n1 - Henrique\n2 - Dona Onça 🐆"
            )
            return

    user = usuarios[telegram_id]

    if "planilha" in texto_lower:
        arquivo = gerar_planilha_profissional(user)

        if arquivo:
            await update.message.reply_document(open(arquivo, "rb"))
        else:
            await update.message.reply_text("🦆 Nenhum gasto encontrado.")
        return

    if "resumo" in texto_lower:
        dados = resumo_mes(user)

        if not dados:
            await update.message.reply_text("🦆 Nenhum gasto no mês ainda.")
            return

        agrupado, total = dados

        msg = f"🦆 {user}:\n\n📊 *RESUMO DO MÊS*\n\n"

        for cat, val in agrupado.items():
            msg += f"• {cat}: R${val:.2f}\n"

        msg += f"\n💰 TOTAL: R${total:.2f}"

        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if "anual" in texto_lower:
        dados = resumo_anual(user)

        if not dados:
            await update.message.reply_text("🦆 Nenhum gasto no ano ainda.")
            return

        agrupado, total = dados

        msg = f"🦆 {user}:\n\n📊 *RESUMO ANUAL*\n\n"

        for cat, val in agrupado.items():
            msg += f"• {cat}: R${val:.2f}\n"

        msg += f"\n💰 TOTAL NO ANO: R${total:.2f}"

        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    try:
        dividir = "dividir" in texto_lower

        resposta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""
Extraia valor, descrição e categoria.

Categorias:
transporte, combustivel, mercado, comida, saude

Retorne JSON válido.

Gasto: {texto}
"""
            }]
        )

        conteudo = resposta.choices[0].message.content.strip()
        conteudo = conteudo.replace("```json", "").replace("```", "").strip()

        dados = json.loads(conteudo)

        if isinstance(dados, dict):
            dados = [dados]

        msg = f"🦆 {user}:\n"

        for g in dados:
            valor = float(g["valor"])

            if dividir:
                metade = valor / 2

                g_user = g.copy()
                g_user["valor"] = metade
                salvar_gasto(g_user, user)

                outro = "Dona Onça 🐆" if user == "Henrique" else "Henrique"

                g_outro = g.copy()
                g_outro["valor"] = metade
                salvar_gasto(g_outro, outro)

                total_cat = total_categoria_mes(user, g["categoria"])

                msg += (
                    f"\n🤝 {g['categoria']} dividido - R${metade:.2f} cada"
                    f"\n📊 Total em {g['categoria']} no mês: R${total_cat:.2f}\n"
                )

            else:
                salvar_gasto(g, user)

                total_cat = total_categoria_mes(user, g["categoria"])

                msg += (
                    f"\n✅ {g['categoria']} - R${valor:.2f}"
                    f"\n📊 Total em {g['categoria']} no mês: R${total_cat:.2f}\n"
                )

        await update.message.reply_text(msg)

    except Exception as e:
        print("Erro:", e)
        await update.message.reply_text("🦆 Não entendi, tenta algo como: mercado 50")


# =========================
# INICIAR
# =========================
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, responder))

print("🤖 Bot rodando...")
app.run_polling()