
# ===============================================================/
# APP CONTROLE FINANCEIRO BY MATHEUS MOREIRA INAMINE ==========/
# ===========================================================/


# =========================
# IMPORT´S
# =========================

import streamlit as st
import pandas as pd
import pdfplumber
import re
import os
import hashlib
import requests
import matplotlib.pyplot as plt
import plotly.express as px
import pickle 
import streamlit.components.v1 as components
import google.generativeai as genai
import sqlite3

# =========================
# FROM´S
# =========================

from datetime import datetime
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
genai.configure(api_key="SUA_CHAVE_AQUI")

# =========================
# CONFIG
# =========================

st.set_page_config(layout="wide")

DB_PATH = "finance.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

#USUARIOS_FILE = "usuarios.json"
#CATEGORIAS_FILE = "categorias.json"
#VINCULOS_FILE = "vinculos.json"
#LOG_FILE = "log_acoes.json"
#METAS_FILE = "metas.json"
#MESADA_FILE = "mesadas.json"

def criar_banco():

    conn = get_conn()
    c = conn.cursor()

    # 👤 USUÁRIOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        senha TEXT,
        tipo TEXT
    )
    """)

    # 💰 LANÇAMENTOS
    c.execute("""
    CREATE TABLE IF NOT EXISTS lancamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        data TEXT,
        descricao TEXT,
        valor REAL,
        categoria TEXT,
        tipo TEXT,
        mes INTEGER,
        ano INTEGER,
        protegido INTEGER DEFAULT 0
    )
    """)

    # 🧠 CATEGORIAS (IA aprende)
    c.execute("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        palavra TEXT,
        categoria TEXT
    )
    """)

    # 📅 CONTAS
    c.execute("""
    CREATE TABLE IF NOT EXISTS contas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        nome TEXT,
        data TEXT,
        tipo TEXT,
        event_id TEXT
    )
    """)

    # 🔗 VÍNCULOS (adulto → dependente)
    c.execute("""
    CREATE TABLE IF NOT EXISTS vinculos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adulto TEXT,
        dependente TEXT
    )
    """)

    # 💰 MESADA
    c.execute("""
    CREATE TABLE IF NOT EXISTS mesadas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        valor REAL,
        dia INTEGER
    )
    """)

    # 🕵️ LOG (ANTI-TRAPAÇA)
    c.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        acao TEXT,
        data TEXT
    )
    """)

    conn.commit()
    conn.close()

criar_banco()

def executar(query, params=(), fetch=False):
    conn = get_conn()
    c = conn.cursor()
    c.execute(query, params)

    if fetch:
        dados = c.fetchall()
        conn.close()
        return dados

    conn.commit()
    conn.close()

DOWNLOADS = str(Path.home() / "Downloads")

SCOPES = ['https://www.googleapis.com/auth/calendar']

def aplicar_estilo():
    st.markdown("""
    <style>

    /* 🔥 FUNDO */
    .stApp {
        background: linear-gradient(135deg, #020617, #020617, #0f172a);
        color: white;
    }

    /* 🔥 CARD */
    .card {
        padding: 35px;
        border-radius: 20px;
        background: rgba(255,255,255,0.03);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 0 60px rgba(0,0,0,0.7);
    }

    /* 🔥 BOTÃO */
    div.stButton > button {
        width: 100%;
        height: 50px;
        border-radius: 12px;
        background: linear-gradient(90deg, #facc15, #eab308);
        color: black;
        font-weight: bold;
        border: none;
    }

    div.stButton > button:hover {
        transform: scale(1.02);
        transition: 0.2s;
    }

    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>

    /* 🔥 COR PRINCIPAL (amarelo padrão do app) */
    :root {
        --primary-color: #facc15;
        --primary-dark: #eab308;
    }

    /* 🔥 TEXTOS IMPORTANTES */
    h1, h2, h3, h4 {
        color: var(--primary-color) !important;
    }

    /* 🔥 LABELS */
    label {
        color: #e5e7eb !important;
    }

    /* 🔥 RADIO BUTTON */
    div[role="radiogroup"] label {
        color: white !important;
    }

    div[role="radiogroup"] input:checked + div {
        background-color: var(--primary-color) !important;
    }

    /* 🔥 INPUT FOCUS */
    input:focus {
        border: 1px solid var(--primary-color) !important;
        box-shadow: 0 0 5px var(--primary-color) !important;
    }

    /* 🔥 METRICS (valores grandes) */
    [data-testid="stMetricValue"] {
        color: var(--primary-color);
    }

    /* 🔥 LINKS */
    a {
        color: var(--primary-color) !important;
    }

    /* 🔥 SLIDER / SELECT */
    .stSlider div {
        color: var(--primary-color);
    }

    </style>
    """, unsafe_allow_html=True)

aplicar_estilo()

# =========================
# DEFINIDOR DE MESADA
# =========================

def definir_mesada(usuario, valor, dia):
    conn = get_conn()
    c = conn.cursor()

    c.execute("DELETE FROM mesadas WHERE usuario=?", (usuario,))

    c.execute(
        "INSERT INTO mesadas (usuario, valor, dia) VALUES (?, ?, ?)",
        (usuario, valor, dia)
    )

    conn.commit()
    conn.close()

def registrar_log(usuario, acao):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "INSERT INTO logs (usuario, acao, data) VALUES (?, ?, ?)",
        (usuario, acao, str(datetime.now()))
    )

    conn.commit()
    conn.close()

# =========================
# GOOGLE OAUTH 2.0
# =========================

def autenticar_google():
    creds = None

    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)
    return service

# =========================
# SESSION STATE
# =========================

if "usuario" not in st.session_state:
    st.session_state.usuario = None

if "tipo" not in st.session_state:
    st.session_state.tipo = "adulto"

if "tela" not in st.session_state:
    st.session_state.tela = "login"  # 🔥 CORRIGIDO

if "chat_ia" not in st.session_state:
    st.session_state.chat_ia = []

if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

if "id_excluir" not in st.session_state:
    st.session_state.id_excluir = None

# =========================
# LOGIN
# =========================

def hash_pwd(p):
    return hashlib.sha256(p.encode()).hexdigest()

def login():

    st.markdown('<div class="card">', unsafe_allow_html=True)

    # ===== LOGO CENTRAL =====
    st.image("icone.ico", width=70)

    # ===== TÍTULO =====
    st.markdown(
        "<h1 style='text-align:center; color:#facc15;'>FinControl</h1>",
        unsafe_allow_html=True
    )

    st.markdown(
        "<p style='text-align:center; color:#94a3b8;'>Controle Financeiro Inteligente</p>",
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ===== FORM =====
    mode = st.radio("Opção", ["Entrar", "Cadastrar"], horizontal=True)

    user = st.text_input("Usuário")
    pwd = st.text_input("Senha", type="password")

    conn = get_conn()
    c = conn.cursor()

    if mode == "Entrar":

            if st.button("Entrar"):

                c.execute("SELECT senha, tipo FROM usuarios WHERE username=?", (user,))
                result = c.fetchone()

                if result and result[0] == hash_pwd(pwd):
                    st.session_state.usuario = user
                    st.session_state.tipo = result[1]
                    st.session_state.tela = "dashboard"
                    st.rerun()
                else:
                    st.error("Login inválido")


    else:

            if st.button("Criar conta"):

                try:
                    c.execute(
                        "INSERT INTO usuarios (username, senha, tipo) VALUES (?, ?, ?)",
                        (user, hash_pwd(pwd), "adulto")
                    )
                    conn.commit()
                    st.success("Conta criada!")
                except:
                    st.warning("Usuário já existe")

    conn.close()

    st.markdown('</div>', unsafe_allow_html=True)

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

def limpar_texto(txt):
    txt = txt.lower()
    txt = re.sub(r'[^a-z0-9\s]', '', txt)  # remove símbolos
    txt = re.sub(r'\s+', ' ', txt)         # espaços duplicados
    return txt.strip()

def categorizar(desc):

    conn = get_conn()
    c = conn.cursor()

    desc_limpa = limpar_texto(desc)

    c.execute("SELECT palavra, categoria FROM categorias")
    dados = c.fetchall()

    conn.close()

    for palavra, categoria in dados:
        palavra_limpa = limpar_texto(palavra)

        if palavra_limpa in desc_limpa:
            return categoria

    return "Outros"

def aprender(df):
    conn = get_conn()
    c = conn.cursor()

    for _, row in df.iterrows():
        if row["Categoria"] and row["Categoria"] != "Outros":
            c.execute(
                "INSERT INTO categorias (palavra, categoria) VALUES (?, ?)",
                (row["Descrição"].lower()[:50], row["Categoria"])
            )

    conn.commit()
    conn.close()

# =========================
# HISTÓRICO
# =========================
def salvar_lancamento(usuario, data, descricao, valor, categoria, tipo, mes, ano, protegido=0):
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        INSERT INTO lancamentos 
        (usuario, data, descricao, valor, categoria, tipo, mes, ano, protegido)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (usuario, data, descricao, valor, categoria, tipo, mes, ano, protegido))

    conn.commit()
    conn.close()

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

def extrair(texto, banco=None):

    # =========================
    # PRÉ-PROCESSAMENTO PESADO
    # =========================

    texto = texto.replace("\r", "")

    # remove espaços duplicados
    texto = re.sub(r'[ \t]+', ' ', texto)

    # junta linhas quebradas (descrições)
    texto = re.sub(r'\n(?!\d{2}/\d{2})', ' ', texto)

    linhas = list(dict.fromkeys(texto.split("\n")))  # remove duplicadas

    dados = []

    # =========================
    # REGEX UNIVERSAL FORTE
    # =========================
    padrao = re.compile(
        r'(\d{2}/\d{2})\s+'
        r'(.+?)\s+'
        r'(-?\d[\d\.\s]*,\d{2})'
    ) # valor (com milhar)
    

    for linha in linhas:

        linha = linha.strip()

        if not linha or len(linha) < 5:
            continue

        linha_lower = linha.lower()

        # 🔥 IGNORAR PAGAMENTOS DA FATURA ANTERIOR
        if "pagamento" in linha_lower:
            continue

        if "pagamento efetuado" in linha_lower:
            continue

        if "deb automatic" in linha_lower:
            continue

        if "total dos pagamentos" in linha_lower:
            continue

        # =========================
        # FILTROS IMPORTANTES
        # =========================
        if linha_lower.startswith("total"):
            continue

        if "lançamento futuro" in linha_lower:
            continue

        # 🔥 lixo comum de fatura Itaú
        if any(p in linha_lower for p in [
            "pagamento",
            "saldo anterior",
            "limite",
            "disponivel",
            "encargos",
            "juros",
            "anuidade",
            "iof",
            "tarifa",
            "mora",
        ]):
            continue

        # =========================
        # MATCH
        # =========================
        match = padrao.search(linha)

        if match:
            data, desc, valor = match.groups()

            match_parcela = re.search(r'(\d{2})/(\d{2})', desc)

            if match_parcela:
                parcela = int(match_parcela.group(1))
                
                # ignora parcelas claramente futuras
                if parcela >= 5:
                    continue

            # limpeza valor
            valor = valor.replace(" ", "")  # 🔥 remove espaços no meio do número
            valor = re.sub(r'[^\d,.-]', '', valor)
            valor = valor.replace(".", "").replace(",", ".")
    
            try:
                valor = float(valor)
            except:
                continue

            # filtro extra (lixo)
            if abs(valor) < 0.01:
                continue

            # limpa descrição
            desc = desc.strip()

            # remove múltiplos espaços
            desc = re.sub(r'\s+', ' ', desc)

            dados.append([data, desc])

    df = pd.DataFrame(dados, columns=["Data", "Descrição"])
    df["Valor"] = 0.0

    # =========================
    # PÓS-PROCESSAMENTO
    # =========================
    if not df.empty:
        df = df.drop_duplicates()

        # remove descrições muito curtas (lixo)
        df = df[df["Descrição"].str.len() > 2]

    valor_fatura = st.number_input("Valor total da fatura (confirmação)")

    return df

# =========================
# UPLOAD
# =========================

def upload():

    st.title("📂 Upload de Fatura")

    file = st.file_uploader("Envie o PDF", type="pdf")

    col1, col2, col3 = st.columns(3)

    mes = col1.selectbox("Mês", list(range(1, 13)))
    ano = col2.number_input("Ano", 2000, 2100, datetime.now().year)

    banco = col3.selectbox(
    "🏦 Banco da fatura",
    ["Selecione...", "Nubank", "Inter", "Itaú", "Santander", "Caixa", "Outro"]
)

    bloquear = banco == "Selecione..."

    if bloquear:
        st.warning("Selecione um banco antes de continuar")

    if file:
        with pdfplumber.open(file) as pdf:
            text = "".join([p.extract_text() or "" for p in pdf.pages])

        df = extrair(text, banco)

        if df.empty:
            st.warning("Nenhum dado encontrado")
            return

        df["Categoria"] = df["Descrição"].apply(categorizar)

        df["Mes"] = mes
        df["Ano"] = ano

        st.subheader("✏️ Edite manualmente")
        df_editado = st.data_editor(df, use_container_width=True, num_rows="dynamic")

        df["Categoria"] = df["Descrição"].apply(categorizar)

        total_fatura = st.number_input("💰 Valor total da fatura", min_value=0.0, step=0.01)

        if total_fatura > 0:

            contagem = df_editado["Categoria"].value_counts()
            total_lanc = contagem.sum()

            valores_por_categoria = {}

            for cat, qtd in contagem.items():
                proporcao = qtd / total_lanc
                valores_por_categoria[cat] = total_fatura * proporcao

            # 🔥 DISTRIBUIÇÃO REAL NOS LANÇAMENTOS
            df_editado["Valor"] = df_editado["Categoria"].apply(
                lambda cat: valores_por_categoria.get(cat, 0) / contagem[cat]
            )

            # 🔥 só pra visualização (opcional)
            df_resumo = pd.DataFrame([
                {"Categoria": cat, "Valor": val}
                for cat, val in valores_por_categoria.items()
            ])

            st.subheader("📊 Distribuição estimada")
            st.dataframe(df_resumo)

            fig = px.pie(df_resumo, names="Categoria", values="Valor")
            st.plotly_chart(fig)

        if st.button("💾 Salvar tudo", disabled=bloquear):
                # aprende categorias (mantém isso)
            aprender(df_editado)

                # salva fatura como lançamento único
            salvar_fatura_como_lancamento(total_fatura, banco, mes, ano)

                # gera PDF (opcional manter detalhado)
            gerar_pdf(df_editado)

            st.success(f"Fatura registrada como lançamento único")

            st.success("Dados salvos com sucesso!")
    voltar()

def salvar_fatura_como_lancamento(total, banco, mes, ano):

    salvar_lancamento(
        st.session_state.usuario,
        f"{ano}-{mes:02d}-01",
        f"Cartão de Crédito - {banco}",
        -abs(total),
        "Cartão de Crédito",
        "Despesa",
        mes,
        ano
    )

# =========================
# DASHBOARD
# =========================

def dashboard():

    usuario = st.session_state.get("usuario", "Usuário")
    tipo = st.session_state.get("tipo", "adulto")

    st.title(f"🏠 Dashboard - {usuario} - {tipo}")
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)
    col5, col6 = st.columns(2)
    col7, col8 = st.columns(2)

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

    if col7.button("📘 Sobre o App", use_container_width=True, key="btn_sobre"):
        st.session_state.tela = "sobre"
        st.rerun()

    if col6.button("📅 Vencimentos", use_container_width=True):
        st.session_state.tela = "vencimentos"
        st.rerun()
    
    if st.session_state.get("tipo") == "adulto":
        if col8.button("⚙️ Controle de Contas de Crianças", use_container_width=True):
            st.session_state.tela = "admin"
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
    st.markdown("---")

    col1, col2 = st.columns(2)

    # 🔁 TROCAR USUÁRIO (logout)
    if col1.button("🔄 Trocar usuário", use_container_width=True):
        logout()

    # ❌ SAIR DO APP (opcional manter)
    if col2.button("🚪 Fechar app", use_container_width=True):
        os._exit(0)


# =========================
# HISTÓRICO VIEW
# =========================

def historico():

    st.title("📊 Histórico")

    conn = get_conn()

    df = pd.read_sql(
        "SELECT * FROM lancamentos WHERE usuario=?",
        conn,
        params=(st.session_state.usuario,)
    )

    conn.close()

    if df.empty:
        st.warning("Sem histórico ainda")
        voltar()
        return

    df["Tipo"] = df["valor"].apply(lambda x: "Receita" if x > 0 else "Despesa")

    meses = sorted(df["mes"].unique())
    anos = sorted(df["ano"].unique())

    col1, col2 = st.columns(2)

    mes_sel = col1.selectbox("Mês", meses)
    ano_sel = col2.selectbox("Ano", anos)

    df = df[(df["mes"] == mes_sel) & (df["ano"] == ano_sel)]

    st.dataframe(df)
    # garante que valor é número
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)

    receitas = df[df["valor"] > 0]["valor"].sum()
    despesas = abs(df[df["valor"] < 0]["valor"].sum())

    if receitas == 0 and despesas == 0:
        st.info("Sem dados para gráfico")
    else:
        fig, ax = plt.subplots()

        ax.pie(
            [receitas, despesas],
            labels=["Receitas", "Despesas"],
            autopct="%1.1f%%",
            colors=["green", "red"]  # 🔥 AQUI
                )

        st.pyplot(fig)

    voltar()

# =========================
# IA
# =========================

def gerar_contexto_financeiro():

    conn = get_conn()

    df = pd.read_sql(
        "SELECT * FROM lancamentos WHERE usuario=? ORDER BY id DESC LIMIT 80",
        conn,
        params=(st.session_state.usuario,)
    )

    conn.close()

    if df.empty:
        return "Sem dados."

    linhas = [
        f"{r['data']} | {r['descricao']} | R$ {r['valor']}"
        for _, r in df.iterrows()
    ]

    return "\n".join(linhas)


def ia_responder(msg):

    tipo_usuario = st.session_state.get("tipo", "adulto")

    contexto = gerar_contexto_financeiro()

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=AIzaSyCYwscpAjTIuH3Vmd3BVwAv4pnvKkcTFSM"

    if tipo_usuario == "criança":
        estilo = """
    Você está falando com uma criança ou adolescente.

    Regras:
    - Use linguagem simples e clara
    - Explique como se estivesse ensinando
    - Use analogias do dia a dia (mesada, jogos, comida, etc)
    - Evite termos técnicos
    - Seja didático e educativo
    - Sempre explique o PORQUÊ das coisas
    - Pode usar exemplos divertidos

    Objetivo:
    Ensinar educação financeira de forma fácil e intuitiva.
    """
    if tipo_usuario == "adolescente":
        estilo = """
    Você está falando com um adolescente.

    Regras:
    - Seja direto e prático
    - Use uma abordagem mais adulta, mas ainda jovem
    - Use linguagem levemente profissional, mas com um toque jovem
    - Aponte problemas e soluções claramente e de forma descontraida
    - Seja objetivo e técnico, mas de forma descontraida e jovem
    """
    if tipo_usuario == "adulto":
        estilo = """
    Você está falando com um adulto.

    Regras:
    - Seja direto e prático
    - Foque em análise financeira real
    - Use linguagem profissional
    - Aponte problemas e soluções claramente
    - Pode ser mais técnico
    """

    prompt = f"""
Você é um especialista financeiro.

Use os dados reais do usuário abaixo para responder de forma personalizada:

{contexto}

Pergunta do usuário:
{msg}

{estilo}

Responda de forma clara, prática e com sugestões reais e conforme o tipo de usuário: .
"""

    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    response = requests.post(url, json=body)

    if response.status_code == 200:
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    return f"Erro {response.status_code}: {response.text}"

def ia():

    st.title("🤖 IA Financeira")

    msg = st.text_area("Pergunte:")

    if st.button("🗑 Limpar chat"):
        st.session_state.chat_ia = []
        st.rerun()


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

#def ia():

    #st.warning("🚧 Função em Manutenção")

    #st.markdown("""
    ### ⚠️ Status

    #A funcionalidade de Inteligência Artificial está em Manutenção.

    #📅 **Reativação prevista:** Versão 3.00 Beta

    #---

    #Motivo da manutenção: Troca do fornecedor de IA 
    #""")

    #voltar()

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

    if st.button("Salvar lançamento"):

        tipo_user = st.session_state.tipo

        # 🔒 BLOQUEIO CRIANÇA
        if tipo_user == "criança" and tipo == "Receita":
            st.error("❌ Crianças não podem lançar receitas")
            return
    
        valor_final = valor if tipo == "Receita" else -valor

        salvar_lancamento(
            st.session_state.usuario,
            str(data),
            descricao,
            valor_final,
            categoria if categoria else tipo,
            tipo,
            data.month,
            data.year
        )

        st.success("Lançamento salvo!")
        st.rerun()

    # =========================
    # 🔥 BUSCAR DADOS (ANTES DE USAR df)
    # =========================
    conn = get_conn()

    df = pd.read_sql(
        "SELECT * FROM lancamentos WHERE usuario=?",
        conn,
        params=(st.session_state.usuario,)
    )

    conn.close()

    # =========================
    # 🔥 VALIDAÇÃO
    # =========================
    if df.empty:
        st.info("Sem lançamentos ainda")
        voltar()
        return

    st.dataframe(df)

    # =========================
    # 🔥 EXCLUSÃO COM PROTEÇÃO
    # =========================
    st.subheader("🗑 Excluir lançamento")

    id_lanc = st.selectbox("Selecione o ID", df["id"])

    if st.button("Excluir"):

        st.session_state.id_excluir = id_lanc

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT protegido FROM lancamentos WHERE id=?", (id_lanc,))
        result = c.fetchone()

        conn.close()

        if not result:
            st.error("Lançamento não encontrado")
            return

        protegido = result[0]
        tipo_user = st.session_state.tipo

        if protegido == 1 and tipo_user == "adolescente":
            st.session_state.auth_ok = False
            st.session_state["pedindo_auth"] = True
            st.rerun()

        elif protegido == 1 and tipo_user == "criança":
            st.error("❌ Você não pode excluir esse lançamento")

        else:
            # adulto ou não protegido
            conn = get_conn()
            c = conn.cursor()

            c.execute("DELETE FROM lancamentos WHERE id=?", (id_lanc,))
            conn.commit()
            conn.close()

            st.success("Excluído!")
            st.rerun()

    if st.session_state.get("pedindo_auth"):

        with st.form("auth_form"):

            st.warning("🔐 Autorização de adulto necessária")

            user_admin = st.text_input("Usuário adulto")
            pwd_admin = st.text_input("Senha", type="password")

            submitted = st.form_submit_button("Autorizar")

            if submitted:

                conn = get_conn()
                c = conn.cursor()

                c.execute(
                    "SELECT senha, tipo FROM usuarios WHERE username=?",
                    (user_admin.strip(),)
                )

                res = c.fetchone()
                conn.close()

                if not res:
                    st.error("Usuário não encontrado")

                else:
                    senha_db, tipo_db = res

                    if tipo_db != "adulto":
                        st.error("Apenas adultos podem autorizar")

                    elif senha_db != hash_pwd(pwd_admin.strip()):
                        st.error("Senha incorreta")

                    else:
                        st.session_state.auth_ok = True
                        st.session_state.pedindo_auth = False
                        st.rerun()
    
    if st.session_state.get("auth_ok"):

        id_real = st.session_state.get("id_excluir")

        conn = get_conn()
        c = conn.cursor()

        c.execute("DELETE FROM lancamentos WHERE id=?", (id_real,))
        conn.commit()
        conn.close()

        st.success("✅ Exclusão autorizada e realizada")

        # limpa estado
        st.session_state.auth_ok = False
        st.session_state.id_excluir = None

        st.rerun()

    voltar()

# =========================
# RELATORIOS
# =========================

def relatorio():

    st.title("📈 Relatório Financeiro")

    conn = get_conn()

    df = pd.read_sql(
        "SELECT * FROM lancamentos WHERE usuario=?",
        conn,
        params=(st.session_state.usuario,)
    )

    conn.close()

    if df.empty:
        st.warning("Sem dados")
        voltar()
        return

    receitas = df[df["valor"] > 0]["valor"].sum()
    despesas = abs(df[df["valor"] < 0]["valor"].sum())
    saldo = receitas - despesas

    col1, col2, col3 = st.columns(3)

    col1.metric("Receitas", f"R$ {receitas:.2f}")
    col2.metric("Despesas", f"R$ {despesas:.2f}")
    col3.metric("Saldo", f"R$ {saldo:.2f}")

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
# Google Calendar
# =========================

def criar_evento_calendar(service, titulo, data, recorrente=False):

    event = {
        'summary': titulo,
        'start': {'date': data},
        'end': {'date': data},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 1440},
                {'method': 'email', 'minutes': 1440}
            ]
        }
    }

    if recorrente:
        event['recurrence'] = ['RRULE:FREQ=MONTHLY']

    evento = service.events().insert(
        calendarId='primary',
        body=event
    ).execute()

    return evento["id"]

def contas_vencimento():

    st.title("📅 Contas e Vencimentos")

    user = st.session_state.usuario

    tipo = st.selectbox(
        "Tipo de vencimento",
        ["Fixo (todo mês)", "Variável"]
    )

    nome = st.text_input("Nome da conta")
    data = st.date_input("Data de vencimento")

    conn = get_conn()
    c = conn.cursor()

    if st.button("Salvar conta"):

        c.execute("""
            INSERT INTO contas (usuario, nome, data, tipo, event_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user, nome, str(data), tipo, None))

        conn.commit()
        st.success("Conta salva!")

    st.markdown("---")
    st.subheader("📋 Contas cadastradas")

    c.execute("SELECT id, nome, data, tipo, event_id FROM contas WHERE usuario=?", (user,))
    contas = c.fetchall()

    for conta in contas:

        col1, col2, col3 = st.columns([3,2,2])

        col1.write(conta[1])
        col2.write(conta[2])

        if col3.button("📅 Calendar", key=f"cal_{conta[0]}"):

            try:
                service = autenticar_google()

                recorrente = conta[3] == "Fixo (todo mês)"

                event_id = criar_evento_calendar(
                    service,
                    conta[1],
                    conta[2],
                    recorrente
                )

                c.execute(
                    "UPDATE contas SET event_id=? WHERE id=?",
                    (event_id, conta[0])
                )

                conn.commit()
                st.success("Evento criado!")

            except Exception as e:
                st.error(str(e))

        if col3.button("❌ Excluir", key=f"del_{conta[0]}"):
            # 🔥 CORREÇÃO: Puxa o event_id (que é o índice 4) e deleta no Google antes de apagar no DB
            event_id = conta[4]
            if event_id:
                try:
                    service = autenticar_google()
                    deletar_evento_calendar(service, event_id)
                except Exception as e:
                    st.warning("Aviso: Não foi possível excluir no Google Calendar.")

            c.execute("DELETE FROM contas WHERE id=?", (conta[0],))
            conn.commit()

            st.success("Removido!")
            st.rerun()

    conn.close()
    voltar()

def deletar_evento_calendar(service, event_id):
    try:
        service.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()
    except:
        pass

# =========================
# PAINEL ADMINISTRAÇÃO
# =========================

def admin():

    st.title("⚙️ Painel de Controle Parental")

    conn = get_conn()
    c = conn.cursor()

    abas = st.tabs(["👤 Usuários", "🗂️ Categorias", "🔗 Vincular", "📊 Sistema",  "💰 Mesada & Presentes", "🧨 Reset"])

    # =========================
    # 👤 USUÁRIOS
    # =========================
    with abas[0]:
        
        conn = get_conn()
        df = pd.read_sql("SELECT * FROM usuarios", conn)
        st.dataframe(df)

        st.subheader("Criar usuário")

        user = st.text_input("Usuário")
        pwd = st.text_input("Senha", type="password")
        tipo = st.selectbox("Tipo", ["adulto", "criança", "adolescente"])

        if st.button("Criar"):
            if not user or not pwd:
                st.warning("Preencha usuário e senha")
            else:
                try:
                    conn = get_conn()
                    c = conn.cursor()

                    c.execute(
                        "INSERT INTO usuarios (username, senha, tipo) VALUES (?, ?, ?)",
                        (user.strip(), hash_pwd(pwd), tipo)
                    )

                    conn.commit()
                    conn.close()

                    st.success("Usuário criado com sucesso!")
                    st.rerun()

                except sqlite3.IntegrityError:
                    st.error("Usuário já existe")

                except Exception as e:
                    st.error(f"Erro ao criar usuário: {e}")

        st.subheader("Excluir usuário")

        if not df.empty:
            user_del = st.selectbox("Selecionar", df["username"])

        if st.button("Excluir usuário"):
            conn = get_conn()
            c = conn.cursor()

            try:
                # 🔥 Remove dados relacionados primeiro
                c.execute("DELETE FROM lancamentos WHERE usuario=?", (user_del,))
                c.execute("DELETE FROM contas WHERE usuario=?", (user_del,))
                c.execute("DELETE FROM mesadas WHERE usuario=?", (user_del,))
                c.execute("DELETE FROM vinculos WHERE adulto=? OR dependente=?", (user_del, user_del))
                c.execute("DELETE FROM logs WHERE usuario=?", (user_del,))

                # 🔥 Agora remove o usuário
                c.execute("DELETE FROM usuarios WHERE username=?", (user_del,))

                conn.commit()
                st.success("Usuário removido com sucesso!")

                st.rerun()

            except Exception as e:
                st.error(f"Erro ao excluir: {e}")

            finally:
                
                conn.close()

        st.subheader("Alterar tipo de usuário")

        usuarios_df = pd.read_sql("SELECT username, tipo FROM usuarios", get_conn())

        user_edit = st.selectbox("Usuário", usuarios_df["username"], key="edit_user")

        tipo_atual = usuarios_df[usuarios_df["username"] == user_edit]["tipo"].values[0]

        novo_tipo = st.selectbox(
            "Novo tipo",
            ["adulto", "adolescente", "criança"],
            index=["adulto", "adolescente", "criança"].index(tipo_atual)
        )

        if st.button("Atualizar tipo"):

            conn = get_conn()
            c = conn.cursor()

            try:
                c.execute(
                    "UPDATE usuarios SET tipo=? WHERE username=?",
                    (novo_tipo, user_edit)
                )
                conn.commit()
                st.success("Tipo atualizado!")
                st.rerun()

            except Exception as e:
                st.error(f"Erro: {e}")

            finally:
                conn.close()

        st.markdown("---")
        st.subheader("📥 Exportar relatório do usuário")

        usuarios_df = pd.read_sql("SELECT username FROM usuarios", get_conn())

        usuario_sel = st.selectbox("Selecionar usuário", usuarios_df["username"])

        col1, col2 = st.columns(2)

        data_inicio = col1.date_input("Data início")
        data_fim = col2.date_input("Data fim")

        if st.button("Gerar relatório"):

            df = buscar_lancamentos_usuario(
                usuario_sel,
                str(data_inicio),
                str(data_fim)
            )

            if df.empty:
                st.warning("Nenhum dado no período")
            else:
                st.dataframe(df)

                col_pdf, col_excel = st.columns(2)

                if col_pdf.button("📄 Baixar PDF"):
                    exportar_pdf_usuario(df, usuario_sel)

                if col_excel.button("📊 Baixar Excel"):
                    exportar_excel_usuario(df, usuario_sel)

    with abas[1]:

        conn = get_conn()
        st.subheader("🗂️ Categorias")

        conn = get_conn()
        df_cat = pd.read_sql("SELECT * FROM categorias", conn)

        st.dataframe(df_cat)

        st.markdown("---")
        st.subheader("➕ Nova categoria")

        palavra = st.text_input("Palavra-chave")
        categoria = st.text_input("Categoria")

        if st.button("Adicionar"):
            conn.execute(
                "INSERT INTO categorias (palavra, categoria) VALUES (?, ?)",
                (palavra.lower(), categoria)
            )
            conn.commit()
            st.success("Adicionado!")
            st.rerun()

        st.markdown("---")
        st.subheader("❌ Remover categoria")

        if not df_cat.empty:
            cat_id = st.selectbox("Selecione", df_cat["id"])

            if st.button("Excluir categoria"):
                conn.execute("DELETE FROM categorias WHERE id=?", (cat_id,))
                conn.commit()
                st.success("Removido!")
                st.rerun()

        conn.close()

    # =========================
    # 🔗 VINCULAR
    # =========================
    with abas[2]:

        conn = get_conn()
        c = conn.cursor()

        usuarios_df = pd.read_sql("SELECT username, tipo FROM usuarios", conn)

        adultos = usuarios_df[usuarios_df["tipo"] == "adulto"]["username"].tolist()
        deps = usuarios_df[usuarios_df["tipo"] != "adulto"]["username"].tolist()

        adulto = st.selectbox("Adulto", adultos)
        dep = st.selectbox("Dependente", deps)

        if st.button("Vincular"):

            if not adulto or not dep:
                st.warning("Selecione ambos os usuários")
            else:
                # 🔥 CORREÇÃO: Verifica se o dependente já possui vínculo
                c.execute("SELECT * FROM vinculos WHERE dependente=?", (dep,))
                if c.fetchone():
                    st.error(f"O dependente '{dep}' já está vinculado a um adulto!")
                else:
                    try:
                        c.execute(
                            "INSERT INTO vinculos (adulto, dependente) VALUES (?, ?)",
                            (adulto, dep)
                        )
                        conn.commit()
                        st.success("Vinculado com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao vincular: {e}")

        # 🔥 Mostrar vínculos
        df_vinculos = pd.read_sql("SELECT * FROM vinculos", conn)
        st.dataframe(df_vinculos)

        conn.close()

    # =========================
    # 📊 SISTEMA
    # =========================
    with abas[3]:

        conn = get_conn()
        total_users = pd.read_sql("SELECT COUNT(*) as total FROM usuarios", conn)["total"][0]
        total_lanc = pd.read_sql("SELECT COUNT(*) as total FROM lancamentos", conn)["total"][0]

        st.metric("Usuários", total_users)
        st.metric("Lançamentos", total_lanc)
        conn.close()


    with abas[4]:

        st.subheader("💰 Lançamentos para Dependentes")

        conn = get_conn()

        usuarios_df = pd.read_sql("SELECT username, tipo FROM usuarios", conn)

        dependentes = usuarios_df[usuarios_df["tipo"] != "adulto"]["username"]

        usuario_sel = st.selectbox("Selecionar dependente", dependentes)

        tipo_lanc = st.selectbox("Tipo", ["Mesada", "Presente"])

        valor = st.number_input("Valor", 0.0)
        descricao = st.text_input("Descrição")

        if st.button("Lançar"):

            if valor <= 0:
                st.warning("Valor inválido")
            else:

                desc_final = f"{tipo_lanc}: {descricao}" if descricao else tipo_lanc

                salvar_lancamento(
                    usuario_sel,
                    str(datetime.now()),
                    desc_final,
                    valor,
                    tipo_lanc,
                    "Receita",
                    datetime.now().month,
                    datetime.now().year,
                    protegido=1  # 🔥 BLOQUEADO
                )

                registrar_log(usuario_sel, f"{tipo_lanc} recebido: R$ {valor}")

                st.success("Lançamento realizado!")

        conn.close()

    # =========================
    # 🧨 RESET
    # =========================
    with abas[5]:
        
        conn = get_conn()
        st.warning("⚠️ Isso apagará TODOS os dados!")

        confirm = st.checkbox("Confirmo que desejo apagar tudo")

        if confirm and st.button("RESETAR SISTEMA"):
            c = conn.cursor()
            c.execute("DELETE FROM usuarios")
            c.execute("DELETE FROM lancamentos")
            c.execute("DELETE FROM categorias")
            c.execute("DELETE FROM contas")
            c.execute("DELETE FROM vinculos")
            c.execute("DELETE FROM mesadas")
            c.execute("DELETE FROM logs")

            conn.commit()
            # 🔥 CORREÇÃO: Limpa os dados do usuário atual e volta para o login
            st.session_state.usuario = None
            st.session_state.tela = "login"
            st.session_state.chat_ia = []
            
            st.success("Sistema resetado! Redirecionando...")
            st.rerun() # Atualiza a página forçando a volta para a tela inicial


    conn.close()
    voltar()

# =========================
# TROCAR USUARIO
# =========================

def logout():
    st.session_state.usuario = None
    st.session_state.tela = "login"
    st.session_state.chat_ia = []
    st.rerun()

# =========================
# VINCULADOR DE USUARIOS
# =========================

def vincular_conta(adulto, adolescente):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "INSERT INTO vinculos (adulto, dependente) VALUES (?, ?)",
        (adulto, adolescente)
    )

    conn.commit()
    conn.close()

# =========================
# BUSCAR LANÇAMENTOS POR USUÁRIO
# =========================
def buscar_lancamentos_usuario(usuario, data_inicio, data_fim):
    conn = get_conn()

    query = """
        SELECT data, descricao, valor, categoria, tipo
        FROM lancamentos
        WHERE usuario = ?
        AND date(data) BETWEEN date(?) AND date(?)
        ORDER BY data ASC
    """

    df = pd.read_sql(query, conn, params=(usuario, data_inicio, data_fim))

    conn.close()

    return df


# =========================
# EXPORTAR BUSCA - PDF
# =========================
def exportar_pdf_usuario(df, usuario):

    nome = f"relatorio_{usuario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    caminho = os.path.join(DOWNLOADS, nome)

    doc = SimpleDocTemplate(caminho)
    styles = getSampleStyleSheet()

    elementos = []

    elementos.append(Paragraph(f"Relatório Financeiro - {usuario}", styles["Title"]))
    elementos.append(Spacer(1, 15))

    receitas = df[df["valor"] > 0]["valor"].sum()
    despesas = abs(df[df["valor"] < 0]["valor"].sum())
    saldo = receitas - despesas

    elementos.append(Paragraph(f"Receitas: R$ {receitas:.2f}", styles["Normal"]))
    elementos.append(Paragraph(f"Despesas: R$ {despesas:.2f}", styles["Normal"]))
    elementos.append(Paragraph(f"Saldo: R$ {saldo:.2f}", styles["Normal"]))
    elementos.append(Spacer(1, 15))

    tabela = [["Data", "Descrição", "Tipo", "Valor", "Categoria"]]

    for _, r in df.iterrows():
        tabela.append([
            str(r["data"]),
            str(r["descricao"]),
            str(r["tipo"]),
            f"R$ {float(r['valor']):.2f}",
            str(r["categoria"])
        ])

    tabela_pdf = Table(tabela)

    elementos.append(tabela_pdf)

    doc.build(elementos)

    st.success(f"PDF gerado em Downloads: {nome}")


# =========================
# EXPORTAR BUSCA - EXCEL
# =========================
def exportar_excel_usuario(df, usuario):

    nome = f"relatorio_{usuario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    caminho = os.path.join(DOWNLOADS, nome)

    df_export = df.copy()

    df_export.rename(columns={
        "data": "Data",
        "descricao": "Descrição",
        "valor": "Valor",
        "categoria": "Categoria",
        "tipo": "Tipo"
    }, inplace=True)

    df_export.to_excel(caminho, index=False)

    st.success(f"Excel gerado em Downloads: {nome}")

# =========================
# ROUTER
# =========================

if st.session_state.usuario is None:
    st.session_state.tela = "login"
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

elif st.session_state.tela == "vencimentos":
    contas_vencimento()

elif st.session_state.tela == "admin":
    admin()

