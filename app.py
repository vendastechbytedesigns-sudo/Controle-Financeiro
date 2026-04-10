import streamlit as st
import pandas as pd
import pdfplumber
import re
import json
import os
import hashlib
import requests
import matplotlib.pyplot as plt
import plotly.express as px
from datetime import datetime
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet

# =========================
# CONFIG
# =========================

st.set_page_config(layout="wide")

USUARIOS_FILE = "usuarios.json"
CATEGORIAS_FILE = "categorias.json"
PASTA_USUARIOS = "usuarios"

DOWNLOADS = str(Path.home() / "Downloads")

os.makedirs(PASTA_USUARIOS, exist_ok=True)

# =========================
# SESSION STATE
# =========================

if "usuario" not in st.session_state:
    st.session_state.usuario = None

if "tela" not in st.session_state:
    st.session_state.tela = "dashboard"

if "chat_ia" not in st.session_state:
    st.session_state.chat_ia = []

# =========================
# JSON
# =========================

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

usuarios = load_json(USUARIOS_FILE)
categorias = load_json(CATEGORIAS_FILE)

# =========================
# LOGIN
# =========================

def hash_pwd(p):
    return hashlib.sha256(p.encode()).hexdigest()

def login():
    st.title("🔐 Login")

    mode = st.radio("Opção", ["Entrar", "Cadastrar"])

    user = st.text_input("Usuário")
    pwd = st.text_input("Senha", type="password")

    if mode == "Entrar":
        if st.button("Entrar"):
            if user in usuarios and usuarios[user] == hash_pwd(pwd):
                st.session_state.usuario = user
                st.session_state.tela = "dashboard"
                st.rerun()
            else:
                st.error("Login inválido")

    else:
        if st.button("Criar conta"):
            usuarios[user] = hash_pwd(pwd)
            save_json(USUARIOS_FILE, usuarios)
            os.makedirs(f"{PASTA_USUARIOS}/{user}", exist_ok=True)
            st.success("Conta criada!")

# =========================
# VOLTAR
# =========================

def voltar():
    st.markdown("---")
    if st.button("⬅ Voltar ao Dashboard"):
        st.session_state.tela = "dashboard"
        st.rerun()

# =========================
# CATEGORIZAÇÃO
# =========================

def categorizar(desc):
    desc = str(desc).lower()
    for k, v in categorias.items():
        if k in desc:
            return v
    return "Outros"

def aprender(df):
    global categorias
    for _, row in df.iterrows():
        if row["Categoria"] and row["Categoria"] != "Outros":
            categorias[str(row["Descrição"]).lower()] = row["Categoria"]
    save_json(CATEGORIAS_FILE, categorias)

# =========================
# HISTÓRICO
# =========================

def salvar_historico(df):

    user = st.session_state.usuario
    path = f"{PASTA_USUARIOS}/{user}/dados.csv"

    os.makedirs(os.path.dirname(path), exist_ok=True)

    df = df.reset_index(drop=True)

    colunas = ["Data", "Descrição", "Valor", "Categoria", "Mes", "Ano"]

    for c in colunas:
        if c not in df.columns:
            df[c] = None

    df = df[colunas]

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

    df = df.dropna(subset=["Descrição", "Valor"])

    df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.strftime("%d/%m/%Y")

    if os.path.exists(path):
        old = pd.read_csv(path)
        df_final = pd.concat([old, df], ignore_index=True)
    else:
        df_final = df

    df_final.to_csv(path, index=False)

# =========================
# PDF
# =========================

def gerar_pdf(df):

    nome = f"relatorio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    caminho = os.path.join(DOWNLOADS, nome)

    doc = SimpleDocTemplate(caminho)
    styles = getSampleStyleSheet()

    content = []
    content.append(Paragraph("Relatório de Gastos", styles["Title"]))
    content.append(Spacer(1, 10))

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    total = df["Valor"].sum()
    content.append(Paragraph(f"Total gasto: R$ {total:.2f}", styles["Normal"]))

    table = [["Data", "Descrição", "Valor", "Categoria"]]

    for _, r in df.iterrows():
        table.append([
            str(r.get("Data", "")),
            str(r.get("Descrição", "")),
            f"R$ {float(r.get('Valor', 0)):.2f}",
            str(r.get("Categoria", "Outros"))
        ])

    content.append(Table(table))
    doc.build(content)

    st.success("PDF salvo em Downloads")

# =========================
# EXTRAÇÃO
# =========================

def extrair(texto):

    linhas = texto.split("\n")

    dados = []
    capturando = False

    for linha in linhas:

        # 👉 COMEÇA a capturar quando entra na seção correta
        if "Lançamentos: compras e saques" in linha:
            capturando = True
            continue

        # 👉 PARA quando chega nas próximas faturas (FUTURO)
        if "Compras parceladas - próximas faturas" in linha:
            break

        if not capturando:
            continue

        linha = linha.strip()

        # 🔥 regex melhorado
        match = re.match(r"(\d{2}/\d{2})\s+(.+?)\s+(-?\d+,\d{2})$", linha)

        if match:
            data, desc, valor = match.groups()

            # 🚫 IGNORAR parcelas tipo "01/10", "02/06" etc
            if re.search(r"\d{2}/\d{2}\s+\d{2}/\d{2}", linha):
                continue

            dados.append([
                data,
                desc.strip(),
                valor
            ])

    df = pd.DataFrame(dados, columns=["Data", "Descrição", "Valor"])

    return df

# =========================
# UPLOAD
# =========================

def upload():

    st.title("📂 Upload de Fatura")

    file = st.file_uploader("Envie o PDF", type="pdf")

    col1, col2 = st.columns(2)
    mes = col1.selectbox("Mês", list(range(1, 13)))
    ano = col2.number_input("Ano", 2000, 2100, datetime.now().year)

    if file:
        with pdfplumber.open(file) as pdf:
            text = "".join([p.extract_text() or "" for p in pdf.pages])

        df = extrair(text)

        if df.empty:
            st.warning("Nenhum dado encontrado")
            return

        df["Valor"] = df["Valor"].str.replace(",", ".").astype(float)
        df["Categoria"] = df["Descrição"].apply(categorizar)

        df["Mes"] = mes
        df["Ano"] = ano

        st.subheader("✏️ Edite manualmente")
        df_editado = st.data_editor(df, use_container_width=True, num_rows="dynamic")

        if st.button("💾 Salvar tudo"):

            df_editado = pd.DataFrame(df_editado)

            aprender(df_editado)
            salvar_historico(df_editado)
            gerar_pdf(df_editado)

            st.success("Dados salvos com sucesso!")

    voltar()

# =========================
# DASHBOARD
# =========================

def dashboard():

    st.title(f"🏠 Dashboard - {st.session_state.usuario}")

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    col5, col6 = st.columns(2)

    if col1.button("📂 Upload - Fatura de Cartão", use_container_width=True, key="btn_upload"):
        st.session_state.tela = "upload"
        st.rerun()

    if col2.button("📊 Histórico - Fatura de Cartão", use_container_width=True, key="btn_historico"):
        st.session_state.tela = "historico"
        st.rerun()

    if col3.button("💰 Lançamentos Manuais", use_container_width=True, key="btn_manual"):
        st.session_state.tela = "manual"
        st.rerun()

    if col4.button("📈 Relatório Financeiro", use_container_width=True, key="btn_relatorio"):
        st.session_state.tela = "relatorio"
        st.rerun()

    if col5.button("🤖 IA Financeira", use_container_width=True, key="btn_ia"):
        st.session_state.tela = "ia"
        st.rerun()

    if col6.button("📘 Sobre o App", use_container_width=True, key="btn_sobre"):
        st.session_state.tela = "sobre"
        st.rerun()

    st.markdown("---")

    # ===== SUPORTE =====
    st.subheader("🛠 Suporte")

    col5, col6, col7 = st.columns(3)

    # WhatsApp
    whatsapp_url = "https://wa.me/5519971392928"
    col5.markdown(f"""
    <a href="{whatsapp_url}" target="_blank">
        <button style="width:100%; height:60px;">💬 WhatsApp</button>
    </a>
    """, unsafe_allow_html=True)

    # Email suporte
    email_suporte = "mailto:matheusmoreirainamine@gmail.com"
    col6.markdown(f"""
    <a href="{email_suporte}">
        <button style="width:100%; height:60px;">📧 Suporte</button>
    </a>
    """, unsafe_allow_html=True)

    # Sugestões
    email_sugestao = "mailto:vendastechbytedesigns@gmail.com"
    col7.markdown(f"""
    <a href="{email_sugestao}">
        <button style="width:100%; height:60px;">💡 Sugestões</button>
    </a>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ===== SAIR =====
    if st.button("🚪 Sair", use_container_width=True, key="btn_sair"):
        st.session_state.usuario = None
        st.session_state.tela = "dashboard"
        st.rerun()

# =========================
# HISTÓRICO VIEW
# =========================

def historico():

    st.title("📊 Histórico")

    path = f"{PASTA_USUARIOS}/{st.session_state.usuario}/dados.csv"

    if not os.path.exists(path):
        st.warning("Sem histórico ainda")
        voltar()
        return

    df = pd.read_csv(path)

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")

    df = df.dropna(subset=["Data"])

    df["Mes"] = pd.to_numeric(df["Mes"], errors="coerce")
    df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce")

    df = df.dropna(subset=["Mes", "Ano"])

    meses = sorted(df["Mes"].unique())
    anos = sorted(df["Ano"].unique())

    col1, col2 = st.columns(2)

    mes_sel = col1.selectbox("📅 Mês", meses)
    ano_sel = col2.selectbox("📅 Ano", anos)

    df = df[(df["Mes"] == mes_sel) & (df["Ano"] == ano_sel)]

    st.dataframe(df)

    resumo = df.groupby("Categoria")["Valor"].sum().reset_index()
    fig = px.bar(resumo, x="Categoria", y="Valor")
    st.plotly_chart(fig)

    voltar()

# =========================
# IA
# =========================

#def gerar_contexto_financeiro():

    path = f"{PASTA_USUARIOS}/{st.session_state.usuario}/dados.csv"

    if not os.path.exists(path):
        return "O usuário ainda não possui histórico financeiro."

    df = pd.read_csv(path)

    if df.empty:
        return "Sem dados suficientes."

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    total = df["Valor"].sum()

    resumo = df.groupby("Categoria")["Valor"].sum().sort_values(ascending=False)

    top_categorias = "\n".join([
        f"- {cat}: R$ {valor:.2f}"
        for cat, valor in resumo.head(5).items()
    ])

    return f"""
Resumo financeiro do usuário:

Total gasto: R$ {total:.2f}

Principais categorias:
{top_categorias}
"""

#def ia_responder(msg):

    msg_lower = msg.lower()

    palavras_financeiras = [
        "dinheiro", "gasto", "economia", "investimento",
        "renda", "cartão", "fatura", "juros",
        "dívida", "orcamento", "poupança", "reserva"
    ]

    if not any(p in msg_lower for p in palavras_financeiras):
        return "❌ Só respondo perguntas sobre finanças."

    contexto = gerar_contexto_financeiro()

    try:
        url = "https://api-inference.huggingface.co/models/google/flan-t5-base"

        prompt = f"""
Você é um especialista financeiro.

Use os dados reais do usuário abaixo para responder de forma personalizada:

{contexto}

Pergunta do usuário:
{msg}

Responda de forma clara, prática e com sugestões reais.
"""

        response = requests.post(
            url,
            json={"inputs": prompt},
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()

            if isinstance(data, list) and "generated_text" in data[0]:
                return data[0]["generated_text"]

        return "⚠️ Erro ao consultar IA online."

    except Exception as e:
        return f"❌ Erro de conexão com IA: {str(e)}"

#def ia():

    st.title("🤖 IA Financeira")

    msg = st.text_area("Pergunte:")

    if st.button("Enviar") and msg.strip():

        st.session_state.chat_ia.append(("user", msg))

        resp = ia_responder(msg)

        st.session_state.chat_ia.append(("ia", resp))

        if len(st.session_state.chat_ia) > 20:
            st.session_state.chat_ia = st.session_state.chat_ia[-20:]

    for role, text in st.session_state.chat_ia:
        if role == "user":
            st.markdown(f"**Você:** {text}")
        else:
            st.markdown(f"**IA:** {text}")

    voltar()
def ia():

    st.title("🤖 IA Financeira")

    st.warning("🚧 Função em desenvolvimento")

    st.markdown("""
### ⚠️ Status

A funcionalidade de Inteligência Artificial ainda está em desenvolvimento.

📅 **Ativação prevista:** Versão 3.00 Beta

---

Enquanto isso, você já pode utilizar:

- 📂 Upload de faturas  
- 📊 Histórico de gastos  
- 📄 Relatórios  

---

💡 Em breve:
- Recomendações financeiras inteligentes  
- Análise automática de gastos  
- Sugestões de economia e investimento  
""")

    voltar()

# =========================
# SOBRE O APP
# =========================

def sobre():

    st.title("📘 Sobre o App")

    st.markdown("""
### 💳 Controle Financeiro Inteligente

Este aplicativo foi desenvolvido com o objetivo de ajudar no controle financeiro pessoal, permitindo:

- 📂 Importar faturas de cartão em PDF  
- 🧠 Classificar automaticamente os gastos  
- ✏️ Editar manualmente os lançamentos, e aprendendo a classificar automáticamente com as alterações manuais  
- 📊 Visualizar histórico de gastos por texto e gráfico 
- 📄 Gerar relatórios em PDF  

---

### 🎯 Objetivo

Facilitar a organização financeira e permitir uma visão clara dos gastos mensais.

---

### 🚀 Futuro

- Integração com IA para recomendações financeiras  
- Suporte a múltiplos bancos  
- Melhorias na análise de dados  

---

### 👨‍💻 Desenvolvedor

Projeto desenvolvido como sistema de controle financeiro pessoal e acadêmico.

---
                
### Mensagem do criador do App - Matheus M. Inamine
    
- Foi muito utilizado os conhecimentos que obtive no meu curso de AI-900, varias noites acordado, muitas doses de sake, e não posso esquecer do meu amigo ChatGPT.
- Escute BUCETA BRADESCO - Rogerio Skylab
""")

    voltar()

# =========================
# LANÇAMENTOS MANUAIS
# =========================

def manual():

    st.title("💰 Lançamentos Manuais")

    tipo = st.selectbox("Tipo", ["Receita", "Despesa"])
    descricao = st.text_input("Descrição")
    valor = st.number_input("Valor", min_value=0.0, step=0.01)
    data = st.date_input("Data")
    categoria = st.text_input("Categoria")

    user = st.session_state.usuario
    path = f"{PASTA_USUARIOS}/{user}/financeiro.csv"

    # =========================
    # SALVAR LANÇAMENTO
    # =========================
    if st.button("Salvar lançamento", key="salvar_manual"):

        novo = pd.DataFrame([{
            "Data": data,
            "Descrição": descricao,
            "Valor": valor if tipo == "Receita" else -valor,
            "Categoria": categoria if categoria else tipo,
            "Tipo": tipo,
            "Mes": data.month,
            "Ano": data.year
        }])

        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                old = pd.read_csv(path)
                df = pd.concat([old, novo], ignore_index=True)
            except:
                df = novo
        else:
            df = novo

        df.to_csv(path, index=False)

        st.success("Lançamento salvo!")
        st.rerun()

    # =========================
    # CARREGAR DADOS
    # =========================
    if os.path.exists(path) and os.path.getsize(path) > 0:

        df = pd.read_csv(path)

    st.subheader("📋 Seus lançamentos")

    # =========================
    # FILTRO MÊS/ANO 🔥
    # =========================
    col1, col2 = st.columns(2)

    mes_filtro = col1.selectbox("Filtrar por mês", ["Todos"] + list(range(1, 13)))
    ano_filtro = col2.selectbox("Filtrar por ano", ["Todos"] + sorted(df["Ano"].dropna().unique().tolist()))

    df_filtrado = df.copy()

    if mes_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Mes"] == mes_filtro]

    if ano_filtro != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Ano"] == ano_filtro]

    # =========================
    # SELEÇÃO
    # =========================
    df_filtrado["Selecionar"] = False

    df_editado = st.data_editor(
        df_filtrado,
        use_container_width=True,
        num_rows="dynamic",
        key="editor_manual"
    )

# =========================
#  # EXCLUIR
# =========================
    if st.button("🗑 Excluir selecionados", key="excluir_manual"):

        ids_para_remover = df_editado[df_editado["Selecionar"] == True]

        if not ids_para_remover.empty:

            df_final = df.merge(ids_para_remover.drop(columns=["Selecionar"]), how="outer", indicator=True)
            df_final = df_final[df_final["_merge"] == "left_only"].drop(columns=["_merge"])

            df_final.to_csv(path, index=False)

            st.success("Lançamentos excluídos!")
            st.rerun()

    else:
        st.info("Nenhum lançamento ainda.")

    voltar()

# =========================
# RELATORIOS
# =========================

def relatorio():

    st.title("📈 Relatório Financeiro")

    user = st.session_state.usuario
    path = f"{PASTA_USUARIOS}/{user}/financeiro.csv"

    if not os.path.exists(path):
        st.warning("Sem dados ainda")
        voltar()
        return

    df = pd.read_csv(path)

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    # separação correta
    receitas_df = df[df["Valor"] > 0].copy()
    despesas_df = df[df["Valor"] < 0].copy()

    receitas = receitas_df["Valor"].sum()
    despesas = abs(despesas_df["Valor"].sum())  # 🔥 IMPORTANTE

    saldo = receitas - despesas

    col1, col2, col3 = st.columns(3)

    col1.metric("💰 Receitas", f"R$ {receitas:.2f}")
    col2.metric("💸 Despesas", f"R$ {despesas:.2f}")
    col3.metric("📊 Saldo", f"R$ {saldo:.2f}")

    st.markdown("---")

    # 🔥 gráfico correto
    resumo = pd.DataFrame({
        "Tipo": ["Receita", "Despesa"],
        "Valor": [receitas, despesas]
    })

    fig = px.pie(resumo, names="Tipo", values="Valor")
    st.plotly_chart(fig)

    if st.button("📄 Gerar Relatório em PDF", key="pdf_financeiro"):
        gerar_relatorio_manual(df)

    voltar()

# =========================
# Relatório Lançamentos Manuais PDF
# =========================


def gerar_relatorio_manual(df):

    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch

    nome = f"relatorio_financeiro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    caminho = os.path.join(DOWNLOADS, nome)

    doc = SimpleDocTemplate(caminho)
    styles = getSampleStyleSheet()

    content = []

    # =========================
    # TÍTULO
    # =========================
    content.append(Paragraph("Relatório Financeiro Completo", styles["Title"]))
    content.append(Spacer(1, 20))

    # =========================
    # GARANTIR DADOS
    # =========================
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

   # GARANTIR COLUNA TIPO
    if "Tipo" not in df.columns:
    # se não existir, assume tudo como despesa (caso da fatura)
     df["Tipo"] = "Despesa"

        # normalizar texto
    df["Tipo"] = df["Tipo"].astype(str)

    receitas = df[df["Tipo"].str.lower() == "receita"]["Valor"].sum()
    despesas = df[df["Tipo"].str.lower() == "despesa"]["Valor"].sum()
    saldo = receitas - despesas

    # =========================
    # RESUMO
    # =========================
    content.append(Paragraph(f"Receitas: R$ {receitas:.2f}", styles["Normal"]))
    content.append(Paragraph(f"Despesas: R$ {despesas:.2f}", styles["Normal"]))
    content.append(Spacer(1, 15))

    cor = colors.green if saldo >= 0 else colors.red

    tabela_resultado = Table(
        [[f"Resultado Final: R$ {saldo:.2f}"]],
        style=[
            ('BACKGROUND', (0, 0), (-1, -1), cor),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]
    )

    content.append(tabela_resultado)
    content.append(Spacer(1, 25))

    # =========================
    # GRÁFICO
    # =========================
    try:
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.pie(
            [receitas, despesas],
            labels=["Receitas", "Despesas"],
            autopct="%1.1f%%"
        )

        grafico_path = os.path.join(DOWNLOADS, "grafico.png")
        plt.savefig(grafico_path)
        plt.close()

        content.append(Paragraph("Receitas vs Despesas", styles["Heading2"]))
        content.append(Spacer(1, 10))
        content.append(Image(grafico_path, width=4*inch, height=4*inch))
        content.append(Spacer(1, 20))

    except:
        content.append(Paragraph("Erro ao gerar gráfico", styles["Normal"]))

    # =========================
    # LISTAGEM COMPLETA (AQUI ESTÁ A CORREÇÃO 🔥)
    # =========================
    content.append(Paragraph("Detalhamento dos Lançamentos", styles["Heading2"]))
    content.append(Spacer(1, 10))

    tabela = [["Data", "Descrição", "Tipo", "Valor"]]

    for _, row in df.iterrows():
        tabela.append([
            str(row.get("Data", "")),
            str(row.get("Descrição", "")),
            str(row.get("Tipo", "")),
            f"R$ {float(row.get('Valor', 0)):.2f}"
        ])

    tabela_dados = Table(tabela, repeatRows=1)

    tabela_dados.setStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
    ])

    content.append(tabela_dados)

    # =========================
    # FINAL
    # =========================
    doc.build(content)

    st.success("Relatório completo gerado com sucesso!")

    from reportlab.lib import colors

    nome = f"relatorio_financeiro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    caminho = os.path.join(DOWNLOADS, nome)

    doc = SimpleDocTemplate(caminho)
    styles = getSampleStyleSheet()

    elementos = []

    # =====================
    # TRATAMENTO
    # =====================
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0)

    receitas = df[df["Valor"] > 0]["Valor"].sum()
    despesas = abs(df[df["Valor"] < 0]["Valor"].sum())
    saldo = receitas - despesas

    # =====================
    # TÍTULO
    # =====================
    elementos.append(Paragraph("Relatório Financeiro Completo", styles["Title"]))
    elementos.append(Spacer(1, 15))

    elementos.append(Paragraph(f"Receitas: R$ {receitas:.2f}", styles["Normal"]))
    elementos.append(Paragraph(f"Despesas: R$ {despesas:.2f}", styles["Normal"]))
    elementos.append(Spacer(1, 10))

    # =====================
    # BARRA RESULTADO
    # =====================
    cor = colors.green if saldo >= 0 else colors.red

    barra = Table([[f"Resultado Final: R$ {saldo:.2f}"]], colWidths=[400])

    barra.setStyle([
        ("BACKGROUND", (0,0), (-1,-1), cor),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.white),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTSIZE", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ("TOPPADDING", (0,0), (-1,-1), 12),
    ])

    elementos.append(barra)
    elementos.append(Spacer(1, 20))

    # =====================
    # 🔥 GRÁFICO REAL (MATPLOTLIB)
    # =====================
    labels = ["Receitas", "Despesas"]
    valores = [receitas, despesas]

    plt.figure()
    plt.pie(valores, labels=labels, autopct="%1.1f%%")
    plt.title("Receitas vs Despesas")

    caminho_img = os.path.join(DOWNLOADS, "grafico_temp.png")
    plt.savefig(caminho_img)
    plt.close()

    from reportlab.platypus import Image
    elementos.append(Image(caminho_img, width=300, height=300))
    elementos.append(Spacer(1, 20))

    # =====================
    # 🔥 LISTA DETALHADA
    # =====================
    elementos.append(Paragraph("Detalhamento dos Lançamentos", styles["Heading2"]))
    elementos.append(Spacer(1, 10))

    tabela = [["Data", "Descrição", "Valor", "Categoria"]]

    for _, r in df.iterrows():
        tabela.append([
            str(r.get("Data", "")),
            str(r.get("Descrição", "")),
            f"R$ {float(r.get('Valor', 0)):.2f}",
            str(r.get("Categoria", ""))
        ])

    tabela_pdf = Table(tabela)

    tabela_pdf.setStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("FONTSIZE", (0,0), (-1,-1), 8),
    ])

    elementos.append(tabela_pdf)

    doc.build(elementos)

    st.success("📄 Relatório completo gerado em Downloads!")

# =========================
# ROUTER
# =========================

if not st.session_state.usuario:
    login()
    st.stop()

if st.session_state.tela == "dashboard":
    dashboard()

elif st.session_state.tela == "upload":
    upload()

elif st.session_state.tela == "historico":
    historico()

elif st.session_state.tela == "ia":
    ia()

elif st.session_state.tela == "sobre":
    sobre()

elif st.session_state.tela == "manual":
    manual()

elif st.session_state.tela == "relatorio":
    relatorio()