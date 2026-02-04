import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
from zoneinfo import ZoneInfo
import re
import base64
import unicodedata
from pathlib import Path
from typing import Optional, Dict, List

# ================= AJUSTES RÁPIDOS (estilo) =================
BTN_HEIGHT = "3.8em"   # Altura de TODOS os botões
BTN_GAP    = "0px"      # Espaçamento vertical unificado
ABAS_SISTEMA = ["PAINEL", "Abordagem", "Tabela UTE", "Escala", "LISTAS"] 
# ============================================================

# --- CONFIG DA PÁGINA ---
st.set_page_config(
    page_title="AppGrandesEventos",
    page_icon="anatel.png",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CONSTANTES ---
TITULO_PRINCIPAL = "AppGrandesEventos"
OBRIG = ":red[**\\***]"

# --- HELPER: NORMALIZAR TEXTO ---
def _normalize_text(s: str) -> str:
    if s is None: return ""
    s = str(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.strip().lower()

# --- MAPA DA CIDADE (Busca Dinâmica de Coordenadas) ---
def get_city_map_url(_client, spreadsheet_id):
    """Busca lat/long nas células AE3/AE4 de qualquer aba de estação e retorna URL do Maps"""
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        # Tenta encontrar a primeira aba que não seja de sistema para colher a coordenada central
        abas_estacoes = [ws for ws in planilha.worksheets() if ws.title not in ABAS_SISTEMA]
        
        if abas_estacoes:
            aba = abas_estacoes[0]
            # Busca Lat em AE3 (Linha 3, Col 31) e Long em AE4 (Linha 4, Col 31)
            lat = aba.cell(3, 31).value
            lon = aba.cell(4, 31).value
            
            if lat and lon:
                # Limpa possíveis espaços ou vírgulas
                lat = str(lat).replace(',', '.').strip()
                lon = str(lon).replace(',', '.').strip()
                return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    except:
        pass
        
    # Fallback caso não encontre coordenadas
    return "https://www.google.com/maps"

IDENT_OPCOES = [
    "Sinal de dados", "Comunicação (voz) relacionada ao evento", "Comunicação (voz) não relacionada ao evento",
    "Sinal não relacionado ao evento", "Espúrio ou Produto de Intermodulação", "Ruído", "Não identificado",
]

FAIXA_OPCOES = ["FM", "SMA", "SMM", "SLP", "TV", "SMP", "GNSS", "Satélite", "Radiação Restrita"]

# --- CONEXÃO GSPREAD ---
@st.cache_resource(ttl=3600, show_spinner=False)
def obter_cliente_gspread():
    try:
        info = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(info, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na autenticação: {e}")
        return None

# --- BUSCA DE PLANILHAS ---
def buscar_planilhas(client):
    if not client: return {}
    try:
        arquivos = client.list_spreadsheet_files()
        planilhas = {}
        termo = "monitoracao"
        
        for arq in arquivos:
            nome_real = arq['name']
            file_id = arq['id']
            nome_norm = ''.join(c for c in unicodedata.normalize('NFD', nome_real) if unicodedata.category(c) != 'Mn').lower()
            
            if termo in nome_norm:
                nome_exibicao = nome_real.replace("Monitoração - ", "").replace("Monitoracao - ", "").replace("MONITORAÇÃO - ", "")
                planilhas[nome_exibicao] = file_id
        
        return planilhas
    except Exception as e:
        st.error(f"Erro ao listar arquivos: {e}")
        return {}

def abrir_planilha_selecionada(_client, spreadsheet_id):
    return _client.open_by_key(spreadsheet_id)

def _img_b64(path: str) -> Optional[str]:
    p = Path(path)
    if not p.exists(): return None
    return base64.b64encode(p.read_bytes()).decode("utf-8")

# --- LISTAR ABAS ---
@st.cache_data(ttl=150, show_spinner=False)
def listar_abas_estacoes(_client, spreadsheet_id):
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        todas = [ws.title for ws in planilha.worksheets()]
        estacoes = [t for t in todas if t not in ABAS_SISTEMA]
        return estacoes
    except:
        return []

# --- HEADER ---
def render_header(imagem_esq: str = "anatel.png", imagem_dir: str = "anatelS.png", show_logout: bool = False):
    # Carrega imagens
    b64_esq = _img_b64(imagem_esq)
    tag_esq = f'<img class="hdr-img" src="data:image/png;base64,{b64_esq}" alt="Logo Esq">' if b64_esq else ""
    
    b64_dir = _img_b64(imagem_dir)
    tag_dir = f'<img class="hdr-img" src="data:image/png;base64,{b64_dir}" alt="Logo Dir">' if b64_dir else ""
    
    evento_atual = st.session_state.get('evento_nome', '')

    # Grid de Imagens e Título
    st.markdown(
        f"""
        <div class="header-grid">
            <div style="text-align: right;">{tag_esq}</div>
            <div class="hdr-title">{TITULO_PRINCIPAL}</div>
            <div style="text-align: left;">{tag_dir}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Subtítulo (Nome do evento) e Botão de Trocar
    if evento_atual:
        if show_logout:
            if st.button(f"Evento selecionado: {evento_atual} 🔄", key="btn_trocar_evento_texto", help="Clique para trocar de evento"):
                for key in ['evento_nome', 'spreadsheet_id', 'view']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        else:
            # AJUSTE 1: Reduzi a margem inferior do texto de 5px para 0px
            st.markdown(
                f"<div style='text-align:center; color:#2E7D32; margin:0; font-size: 0.85rem; font-weight: 600; margin-top: -12px; margin-bottom: 0px; font-family: sans-serif;'>Evento selecionado: {evento_atual}</div>",
                unsafe_allow_html=True
            )

    # AJUSTE 2: Margem superior negativa (-10px) para puxar a linha pra cima
    st.markdown(
        """
        <hr style='
            margin-top: -100px !important; 
            margin-bottom: 2px !important; 
            border: 0; 
            border-top: 1px solid #ccc;
        '>
        """, 
        unsafe_allow_html=True
    )

# --- CSS ---
st.markdown(f"""
<style>
  :root{{ --btn-height: {BTN_HEIGHT}; --btn-gap: {BTN_GAP}; --btn-font: 1.02em; }}
  
  /* --- 1. CONFIGURAÇÃO GERAL (TOPO) --- */
  .block-container {{ 
      max-width: 760px; 
      
      /* 1. ESPAÇO ACIMA DO CABEÇALHO (TETO) */
      padding-top: 10px !important;  /* <<< MEXA AQUI (Tente 0px, 10px, 20px...) */
      
      padding-bottom: 1.9rem; 
      margin: 0 auto;
  }}
  .stApp {{ background-color: #F1F8E9; }}
  #MainMenu, footer, header {{ visibility: hidden; }}
  div[data-testid="stWidgetLabel"] > label {{ color:#000 !important; text-shadow: 0 1px 0 rgba(0,0,0,.05); }}
  
  /* Remove margens padrão de linhas horizontais */
  hr {{ margin-top: 0 !important; margin-bottom: 0 !important; }}

  /* --- 2. CABEÇALHO (DISTÂNCIA ATÉ A LINHA) --- */
  .header-grid {{
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 10px;
      width: 100%;
      
      /* 2. ESPAÇO ENTRE O TÍTULO/LOGOS E A LINHA DE BAIXO */
      margin-bottom: 0px; /* <<< MEXA AQUI (Pode usar negativo ex: -5px) */
  }}
  
  .hdr-img {{ height: 55px; object-fit: contain; }}
  
  .hdr-title {{
      margin: 0; 
      color: #1A311F; 
      font-weight: 800; 
      
      /* MUDANÇA 1: Tamanho aumentado de 1.5rem para 2rem (igual ao COP30) */
      font-size: 1.7rem; 
      
      line-height: 1.1; 
      
      /* MUDANÇA 2: Sombra dupla (branca e preta) para dar o efeito de profundidade */
      text-shadow: 1px 1px 0 rgba(255,255,255,.35), 0 1px 2px rgba(0,0,0,.28);
      
      font-family: sans-serif; 
      text-align: center; 
      white-space: normal;
  }}

  @media (max-width: 480px) {{
      .hdr-img {{ height: 38px; }}
      
      /* MUDANÇA 3: Ajuste mobile proporcional ao COP30 */
      .hdr-title {{ font-size: 1.3rem; }} 
      
      .header-grid {{ gap: 5px; }}
  }}

  /* --- 3. BOTÕES PADRÃO --- */
  .stButton:not(.st-key-btn_trocar_evento_texto) > button, .app-btn, div[data-testid="stLinkButton"] a {{
    width: 100% !important;
    height: var(--btn-height); min-height: var(--btn-height);
    font-size: var(--btn-font) !important; font-weight: 600 !important;
    border-radius: 8px !important; border: 3.4px solid #54515c !important;
    color: white !important; background: linear-gradient(to bottom, #14337b, #4464A7) !important;
    box-shadow: 2px 2px 5px rgba(0,0,0,.3) !important;
    margin: 0 auto var(--btn-gap) auto !important;
    display: flex; align-items: center; justify-content: center;
    text-decoration: none !important;
  }}
  
  div[data-testid="stForm"] .stButton > button:hover {{
    background: linear-gradient(to bottom, #9ccc65, #AED581) !important;
    border-color: #7cb342 !important;
    color: white !important;
  }}

  /* --- 4. TEXTO DE TROCA DE EVENTO --- */
 /* --- 4. TEXTO DE TROCA DE EVENTO --- */
  
  /* Puxa a linha cinza para cima (reduz o espaço das setas azuis) */
  div.stElementContainer:has(div.st-key-btn_trocar_evento_texto) {{
    margin-bottom: -25px !important; 
  }}

  div.stElementContainer:has(div.st-key-btn_trocar_evento_texto),
  div.st-key-btn_trocar_evento_texto {{
    display: flex !important; width: 100% !important;
    justify-content: center !important; align-items: center !important;
    margin-top: -5px;
  }}
  
  /* Estilo do botão em si */
  div.st-key-btn_trocar_evento_texto button {{
    background: transparent !important; 
    border: none !important; 
    box-shadow: none !important;
    color: #2E7D32 !important; 
    font-size: 0.85rem !important; 
    font-weight: 600 !important;
    
    /* --- ALTURA REDUZIDA --- */
    min-height: 0px !important;    /* Destrava a altura mínima */
    height: 26px !important;       /* Define a altura exata (ajuste se quiser menor) */
    padding: 0 !important;         /* Remove enchimento */
    
    /* --- CENTRALIZAÇÃO --- */
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    margin: 0 auto !important;
  }}
  
  /* --- CORREÇÃO CRÍTICA DE CENTRALIZAÇÃO --- */
  /* Remove a margem do texto interno (o <p>) que empurrava o texto para baixo */
  div.st-key-btn_trocar_evento_texto button p {{
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1 !important;
    padding-top: 2px !important; /* Ajuste fino ótico se parecer muito alto */
  }}
  
  div.st-key-btn_trocar_evento_texto button:hover {{
    color: #1b5e20 !important; text-decoration: underline !important;
    transform: scale(1.05) !important; background: transparent !important;
  }}

  /* --- 5. ESPAÇAMENTO DA LINHA PARA O PRIMEIRO BOTÃO --- */
  
  /* O marker-vermelho é o primeiro item. Usamos margem negativa nele para puxar tudo pra cima */
  div[data-testid="stElementContainer"]:has(#marker-vermelho) {{
      
      /* 3. ESPAÇO ENTRE A LINHA E O PRIMEIRO BOTÃO */
      margin-top: -12.5px !important; /* <<< MEXA AQUI (Quanto mais negativo, mais sobe) */
      
      margin-bottom: 0px !important;
      line-height: 0;
  }}

  #marker-vermelho {{ display: none; }}
  
  div[data-testid="stElementContainer"]:has(#marker-vermelho) ~ div[data-testid="stElementContainer"]:nth-of-type(-n+4) .stButton > button {{
    background: linear-gradient(to bottom, #c62828, #e53935) !important; border-color: #a92222 !important;
  }}
  
  div[data-testid="stLinkButton"] a[href*="translate.google.com"],
  div[data-testid="stLinkButton"] a[href*="maps.google"] {{
    background: linear-gradient(to bottom, #2e7d32, #4caf50) !important; border-color: #1b5e20 !important;
  }}
  
  #marker-bsr-erb-form {{ display: none; }}
  div[data-testid="stElementContainer"]:has(#marker-bsr-erb-form) ~ div[data-testid="stElementContainer"] div[data-testid="stForm"] .stButton > button {{
    background: linear-gradient(to bottom, #2e7d32, #4caf50) !important;
    border-color: #1b5e20 !important;
  }}
  
  .confirm-warning{{ background: linear-gradient(to bottom, #f0ad4e, #ec971f); color:#333 !important; font-weight:600; text-align:center; padding:1rem; border-radius:8px; margin-bottom:1rem; border: 1px solid #d58512; }}
  .info-green {{ background: linear-gradient(to bottom, #1b5e20, #2e7d32); color: #fff; font-weight: 700; text-align: center; padding: .8rem 1rem; border-radius: 8px; margin: .25rem 0 1rem; }}
  
  .ute-table {{ width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; }}
  .ute-table th, .ute-table td {{ border: 1px solid #ddd; padding: 8px; text-align: center; }}
  .ute-table th {{ background-color: #f2f2f2; color: #333; }}
  .copyable-cell {{ cursor: pointer; color: #14337b; font-weight: bold; }}
  .copyable-cell:hover {{ text-decoration: underline; background-color: #f0f0f0; }}
</style>
""", unsafe_allow_html=True)

# ===================== HELPERS =====================

def _first_col_match(columns, *preds):
    for c in columns:
        s = (c or "").strip().lower()
        for p in preds:
            if p(s): return c
    return None

def _col_to_index(letter: str) -> int:
    letter = (letter or "").upper()
    res = 0
    for ch in letter:
        if not ('A' <= ch <= 'Z'): continue
        res = res * 26 + (ord(ch) - ord('A') + 1)
    return res

def _first_empty_row_in_block(aba, start_col_letter: str, end_col_letter: str) -> int:
    start_idx = _col_to_index(start_col_letter)
    end_idx   = _col_to_index(end_col_letter)
    max_len = 1
    for idx in range(start_idx, end_idx + 1):
        try:
            vals = aba.col_values(idx)
            if len(vals) > max_len: max_len = len(vals)
        except: pass
    return max_len + 1

def _first_row_where_col_empty(aba, col_letter: str, start_row: int = 2) -> int:
    col_idx = _col_to_index(col_letter)
    try: col_vals = aba.col_values(col_idx)
    except: col_vals = []
    if len(col_vals) < start_row: return start_row
    for i in range(start_row-1, len(col_vals)):
        if (col_vals[i] or "").strip() == "": return i + 1
    return len(col_vals) + 1

def _next_sequential_id(aba, col_letter: str = "H", start_row: int = 2) -> int:
    col_idx = _col_to_index(col_letter)
    try: col_vals = aba.col_values(col_idx)
    except: col_vals = []
    max_id = 0
    for i, v in enumerate(col_vals, start=1):
        if i < start_row: continue
        s = (v or "").strip()
        if not s: continue
        try:
            n = int(s)
            if n > max_id: max_id = n
        except: pass
    return max_id + 1 if max_id >= 0 else 1

def _valid_neg_coord(value: str) -> bool:
    if value is None: return True
    v = value.strip()
    if v == "": return True
    return re.match(r"^-\d+\.\d{6}$", v) is not None

# ===================== FUNÇÕES DE CARGA =====================

@st.cache_data(ttl=150, show_spinner=False)
def carregar_dados_ute(_client, spreadsheet_id):
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        aba = planilha.worksheet("Tabela UTE")
        matriz = aba.get_all_values()
        if not matriz or len(matriz) < 2: return pd.DataFrame()
        dados = []
        for row in matriz[1:]:
            if len(row) > 7:
                dados.append({
                    "País/Entidade": row[0], "Frequência (MHz)": row[4],
                    "Largura (kHz)": row[5], "Processo SEI": row[7]
                })
        df = pd.DataFrame(dados)
        df = df[df["Processo SEI"].str.strip() != ""]
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=150, show_spinner=False)
def carregar_pendencias_painel_mapeadas(_client, spreadsheet_id):
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        aba = planilha.worksheet("PAINEL")
        matriz = aba.get("A1:AF")
        if not matriz or len(matriz) < 2: return pd.DataFrame()

        header, rows = matriz[0], matriz[1:]
        df = pd.DataFrame(rows, columns=header)
        
        def col_like(*checks):
            return _first_col_match(df.columns, *[(lambda s, c=c: c(s)) for c in checks])

        cols_map = {
            'situ': lambda s: s == "situação" or s == "situacao",
            'est': lambda s: "estação" in s or "estacao" in s,
            'id': lambda s: s == "id",
            'fiscal': lambda s: "fiscal" in s,
            'data': lambda s: s == "data" or s == "dia",
            'hora': lambda s: "hh" in s or "hora" in s,
            'freq': lambda s: "frequência" in s or "frequencia" in s,
            'bw': lambda s: "largura" in s,
            'faixa': lambda s: "faixa" in s and "envolvida" in s,
            'ident': lambda s: "identificação" in s,
            'autz': lambda s: "autorizado" in s,
            'ute': lambda s: s.strip() == "ute" or "ute?" in s,
            'proc': lambda s: "processo" in s and "sei" in s,
            'obs': lambda s: "ocorrência" in s or "observa" in s,
            'cient': lambda s: "ciente" in s,
            'inter': lambda s: "interferente" in s
        }
        
        found_cols = {k: col_like(v) for k, v in cols_map.items()}
        
        if not (found_cols['situ'] and found_cols['est'] and found_cols['id']): return pd.DataFrame()

        situ = df[found_cols['situ']].astype(str).str.strip().str.lower()
        pend = df[situ.eq("pendente")].copy()
        if pend.empty: return pd.DataFrame()

        out = pd.DataFrame()
        out["Local"] = pend[found_cols['est']]
        out["EstacaoRaw"] = pend[found_cols['est']]
        out["ID"] = pend[found_cols['id']]
        
        mappings = [
            ("Fiscal", 'fiscal'), ("Data", 'data'), ("HH:mm", 'hora'),
            ("Frequência (MHz)", 'freq'), ("Largura (kHz)", 'bw'),
            ("Faixa de Frequência Envolvida", 'faixa'), ("Identificação", 'ident'),
            ("Autorizado?", 'autz'), ("UTE?", 'ute'), ("Processo SEI UTE", 'proc'),
            ("Ocorrência (observações)", 'obs'), ("Alguém mais ciente?", 'cient'),
            ("Interferente?", 'inter'), ("Situação", 'situ')
        ]
        for dest, key in mappings:
            out[dest] = pend[found_cols[key]] if found_cols[key] else ""

        out = out.sort_values(by=["Local", "Data"], kind="stable", na_position="last").reset_index(drop=True)
        out["Fonte"] = "PAINEL"
        return out
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=150, show_spinner=False)
def carregar_pendencias_abordagem_pendentes(_client, spreadsheet_id):
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        aba = planilha.worksheet("Abordagem")
        matriz = aba.get("H1:W")
        if not matriz or len(matriz) < 2: return pd.DataFrame()

        header, rows = matriz[0], matriz[1:]
        
        def get_col(idx_offset): 
            return pd.Series([r[idx_offset] if len(r)>idx_offset else "" for r in rows])

        pend = pd.DataFrame({
            "Local": get_col(1), # I
            "EstacaoRaw": "ABORDAGEM",
            "ID": get_col(0),    # H
            "Fiscal": get_col(2),# J
            "Data": get_col(3),  # K
            "HH:mm": get_col(4), # L
            "Frequência (MHz)": get_col(5), # M
            "Largura (kHz)": get_col(6),    # N
            "Faixa de Frequência Envolvida": get_col(7), # O
            "Identificação": "",
            "Autorizado?": "", "UTE?": "", "Processo SEI UTE": "",
            "Ocorrência (observações)": get_col(12), # T
            "Alguém mais ciente?": get_col(13), # U
            "Interferente?": get_col(14), # V
            "Situação": get_col(15),      # W
            "Fonte": "ABORDAGEM",
        })

        pend = pend[pend["Situação"].str.strip().str.lower().eq("pendente")].copy()
        pend = pend.sort_values(by=["Local","Data"], kind="stable").reset_index(drop=True)
        return pend
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=150, show_spinner=False)
def carregar_pendencias_todas_estacoes(_client, spreadsheet_id):
    """
    Busca pendências em TODAS as abas de estações.
    Versão OTIMIZADA para coluna padronizada 'Data'.
    """
    try:
        estacoes = listar_abas_estacoes(_client, spreadsheet_id)
        if not estacoes: return pd.DataFrame()

        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        dfs = []

        for nome_aba in estacoes:
            try:
                aba = planilha.worksheet(nome_aba)
                matriz = aba.get_all_values()
                if not matriz or len(matriz) < 2: continue

                # 1. BUSCA INTELIGENTE DO CABEÇALHO
                # Procura linha que tenha "Situação" E ("ID" ou "Data")
                header_idx = 0
                for i in range(min(6, len(matriz))):
                    row_txt = [str(c).lower().strip() for c in matriz[i]]
                    # Verifica se é a linha de cabeçalho
                    if any("situa" in x for x in row_txt) and (any("id" == x for x in row_txt) or any("data" in x for x in row_txt)):
                        header_idx = i
                        break
                
                header = matriz[header_idx]
                rows = matriz[header_idx+1:]
                
                df = pd.DataFrame(rows, columns=header)
                
                def col_like(*checks):
                    return _first_col_match(df.columns, *[(lambda s, c=c: c(s)) for c in checks])

                cols_map = {
                    'est': lambda s: "estação" in s or "estacao" in s or "local" in s,
                    'situ': lambda s: "situação" in s or "situacao" in s,
                    'id': lambda s: s == "id",
                    'fiscal': lambda s: "fiscal" in s,
                    
                    # AQUI FICOU MAIS LIMPO: Busca apenas "data" ou "dia"
                    'data': lambda s: "data" in s or "dia" in s,
                    
                    'hora': lambda s: "hh" in s or "hora" in s,
                    'freq': lambda s: "frequência" in s or "frequencia" in s,
                    'bw': lambda s: "largura" in s,
                    'faixa': lambda s: "faixa" in s,
                    'ident': lambda s: "identificação" in s,
                    'autz': lambda s: "autorizado" in s,
                    'ute': lambda s: "ute" in s,
                    'proc': lambda s: "processo" in s,
                    'obs': lambda s: "ocorrência" in s or "observa" in s,
                    'cient': lambda s: "ciente" in s,
                    'inter': lambda s: "interferente" in s
                }
                
                found = {k: col_like(v) for k, v in cols_map.items()}
                
                if not found['situ']: continue

                situ = df[found['situ']].astype(str).str.strip().str.lower()
                pend = df[situ.eq("pendente")].copy()
                if pend.empty: continue

                out = pd.DataFrame()
                
                # Preenchimento inteligente dos campos principais
                out["ID"] = pend[found['id']] if found['id'] else (pend.iloc[:, 0] if len(pend.columns)>0 else "")
                
                if found['est']: out["Local"] = pend[found['est']]
                elif len(pend.columns) > 1: out["Local"] = pend.iloc[:, 1]
                else: out["Local"] = nome_aba
                
                out["EstacaoRaw"] = nome_aba

                # Data agora deve ser encontrada facilmente
                if found['data']:
                    out["Data"] = pend[found['data']]
                else:
                    # Fallback de segurança ainda útil
                    if len(pend.columns) > 3: out["Data"] = pend.iloc[:, 3] 
                    elif len(pend.columns) > 1: out["Data"] = pend.iloc[:, 1]
                    else: out["Data"] = ""

                mappings = [
                    ("Fiscal", 'fiscal'), ("HH:mm", 'hora'),
                    ("Frequência (MHz)", 'freq'), ("Largura (kHz)", 'bw'),
                    ("Faixa de Frequência Envolvida", 'faixa'), ("Identificação", 'ident'),
                    ("Autorizado?", 'autz'), ("UTE?", 'ute'), ("Processo SEI UTE", 'proc'),
                    ("Ocorrência (observações)", 'obs'), ("Alguém mais ciente?", 'cient'),
                    ("Interferente?", 'inter'), ("Situação", 'situ')
                ]
                
                for dest, key in mappings:
                    out[dest] = pend[found[key]] if found[key] else ""

                out["Fonte"] = "ESTACAO"
                dfs.append(out)

            except: pass
        
        if not dfs: return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)

    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=150, show_spinner=False)
def carregar_todas_frequencias(_client, spreadsheet_id):
    frequencias_map = {}
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        
        # 1. PAINEL (B:G)
        aba_painel = planilha.worksheet("PAINEL")
        dados_painel = aba_painel.get("B2:G")
        for row in dados_painel:
            if len(row) >= 6:
                estacao, freq = row[0], row[5]
                if estacao and freq:
                    try:
                        f_val = round(float(str(freq).replace(",", ".")), 3)
                        if f_val not in frequencias_map:
                            frequencias_map[f_val] = estacao
                    except: pass
        
        # 2. Abordagem (I:M)
        aba_abord = planilha.worksheet("Abordagem")
        dados_abord = aba_abord.get("I2:M")
        for row in dados_abord:
            if len(row) >= 5:
                regiao, freq = row[0], row[4]
                if regiao and freq:
                    try:
                        f_val = round(float(str(freq).replace(",", ".")), 3)
                        if f_val not in frequencias_map:
                            frequencias_map[f_val] = regiao
                    except: pass
    except: pass
    return frequencias_map

# ===================== FUNÇÕES DE ESCRITA =====================

def atualizar_campos_na_aba_mae(_client, spreadsheet_id, estacao_raw, id_ocorrencia, novos_valores: Dict[str, str]) -> str:
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        aba_nome = estacao_raw
        try:
            aba = planilha.worksheet(aba_nome)
        except:
            return f"ERRO: Aba '{aba_nome}' não encontrada na planilha."

        header = aba.row_values(1)
        cell = aba.find(str(id_ocorrencia), in_column=1)
        if not cell: return f"ERRO: ID {id_ocorrencia} não encontrado."
        
        def find_col(*checks):
            for idx, name in enumerate(header, start=1):
                s = (name or "").strip().lower()
                for p in checks:
                    if p(s): return idx
            return None

        cols_idx = {
            "Situação": find_col(lambda s: s == "situação" or s == "situacao"),
            "Identificação": find_col(lambda s: "identificação" in s),
            "Autorizado?": find_col(lambda s: "autorizado" in s),
            "UTE?": find_col(lambda s: "ute" in s),
            "Processo SEI UTE": find_col(lambda s: "processo" in s),
            "Ocorrência (observações)": find_col(lambda s: "ocorrência" in s),
            "Alguém mais ciente?": find_col(lambda s: "ciente" in s),
            "Interferente?": find_col(lambda s: "interferente" in s)
        }

        updates = []
        for key, val in novos_valores.items():
            if key in cols_idx and cols_idx[key]:
                updates.append((cell.row, cols_idx[key], val))

        for r, c, v in updates:
            aba.update_cell(r, c, v)

        return f"Atualizado na aba '{aba.title}'."
    except Exception as e:
        return f"ERRO ao atualizar: {e}"

def atualizar_campos_abordagem_por_id(_client, spreadsheet_id, id_h: str, novos_valores: Dict[str, str]) -> str:
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        aba = planilha.worksheet("Abordagem")
        cell = aba.find(str(id_h), in_column=_col_to_index("H"))
        if not cell: return "Registro não encontrado."
        
        col_map = {
            "Identificação": "P", "Autorizado?": "Q", "UTE?": "R",
            "Processo SEI UTE": "S", "Ocorrência (observações)": "T",
            "Alguém mais ciente?": "U", "Interferente?": "V", "Situação": "W"
        }
        
        for k, v in novos_valores.items():
            if k in col_map:
                aba.update_cell(cell.row, _col_to_index(col_map[k]), v)
        return "Alterações salvas na 'Abordagem'."
    except Exception as e:
        return f"Erro: {e}"

def inserir_emissao_I_W(_client, spreadsheet_id, dados_formulario: Dict[str, str]) -> bool:
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        aba = planilha.worksheet("Abordagem")
        row = _first_row_where_col_empty(aba, "M", start_row=2)
        next_id = _next_sequential_id(aba, col_letter="H", start_row=2)

        dia = dados_formulario.get("Dia")
        if hasattr(dia, "strftime"): dia = dia.strftime("%d/%m/%Y")
        
        hora = dados_formulario.get("Hora")
        if hasattr(hora, "strftime"): hora = hora.strftime("%H:%M")
        
        vals = [
            dados_formulario.get("Local/Região", "Abordagem"),
            dados_formulario.get("Fiscal", ""),
            dia, hora,
            float(dados_formulario.get("Frequência em MHz", 0)),
            float(dados_formulario.get("Largura em kHz", 0)),
            dados_formulario.get("Faixa de Frequência", ""),
            dados_formulario.get("Identificação",""),
            dados_formulario.get("Autorizado? (Q)", ""),
            "Sim" if dados_formulario.get("UTE?") else "Não",
            dados_formulario.get("Processo SEI ou Ato UTE", ""),
            f"{dados_formulario.get('Observações/Detalhes/Contatos','')} - {dados_formulario.get('Responsável pela emissão','')}",
            "", 
            dados_formulario.get("Interferente?",""),
            dados_formulario.get("Situação", "Pendente"),
        ]

        aba.update(f"H{row}", [[str(next_id)]], value_input_option="RAW")
        aba.update(f"I{row}:W{row}", [vals], value_input_option="RAW")
        return True
    except Exception as e:
        st.error(f"Erro inserção: {e}")
        return False

def inserir_bsr_erb(_client, spreadsheet_id, tipo, regiao, lat, lon) -> str:
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        aba = planilha.worksheet("Abordagem")
        row = _first_empty_row_in_block(aba, "X", "AC")
        
        coords = [[lat or "", lon or ""]]
        
        if tipo == "BSR/Jammer":
            aba.update(f"X{row}:Y{row}", [["1", regiao]], value_input_option="USER_ENTERED")
        else:
            aba.update(f"Z{row}:AA{row}", [["1", regiao]], value_input_option="USER_ENTERED")
        
        aba.update(f"AB{row}:AC{row}", coords, value_input_option="USER_ENTERED")
        return f"'{tipo}' incluído com sucesso."
    except Exception as e:
        return f"ERRO: {e}"

@st.cache_data(ttl=3600, show_spinner=False)
def carregar_opcoes_identificacao(_client, spreadsheet_id):
    """Tenta carregar opções de qualquer aba de estação disponível"""
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        todas = planilha.worksheets()
        
        # Procura a primeira aba que não seja do sistema
        aba_alvo = None
        for ws in todas:
            if ws.title not in ABAS_SISTEMA:
                aba_alvo = ws
                break
        
        if aba_alvo:
            # Assume que a validação de dados está na coluna AC (padrão)
            return [i[0] for i in aba_alvo.get('AC3:AC9') if i]
        return ["Opções não encontradas"]
    except:
        return ["Opção genérica (erro leitura)"]

def _buscar_por_texto_livre(client, spreadsheet_id, termos: str, abas: List[str]) -> pd.DataFrame:
    planilha = abrir_planilha_selecionada(client, spreadsheet_id)
    resultados = []
    termos_norm = _normalize_text(termos)

    for nome in abas:
        try:
            aba = planilha.worksheet(nome)
            all_vals = aba.get_all_values()
            if not all_vals: continue
            df = pd.DataFrame(all_vals[1:], columns=all_vals[0])
            df = df.iloc[:, ~df.columns.duplicated()]
            
            # Concatena tudo numa string para busca
            comb = df.fillna("").astype(str).agg(" ".join, axis=1)
            mask = comb.apply(lambda x: termos_norm in _normalize_text(x))
            
            achados = df[mask].copy()
            if not achados.empty:
                achados.insert(0, "Aba/Origem", nome)
                resultados.append(achados)
        except: continue

    if not resultados: return pd.DataFrame()
    return pd.concat(resultados, ignore_index=True)

def render_ocorrencia_readonly(row: pd.Series, key_prefix: str):
    """Renderiza os dados de uma linha de forma organizada e apenas leitura"""
    c1, c2 = st.columns(2)
    
    # Tratamento de campos comuns para evitar erros de nomes de colunas diferentes
    data_val = row.get("Data", row.get("Dia", ""))
    hora_val = row.get("HH:mm", row.get("Hora", ""))
    freq_val = row.get("Frequência (MHz)", row.get("Frequência", ""))
    local_val = row.get("Local", row.get("Local/Região", row.get("Aba/Origem", "")))
    obs_val = row.get("Ocorrência (observações)", row.get("Observações/Detalhes/Contatos", ""))

    with c1:
        st.text_input("Origem/Aba", value=str(row.get("Aba/Origem", "")), disabled=True, key=f"{key_prefix}_orig")
        st.text_input("Local/Estação", value=str(local_val), disabled=True, key=f"{key_prefix}_loc")
        st.text_input("Data", value=str(data_val), disabled=True, key=f"{key_prefix}_dt")
        st.text_input("Hora", value=str(hora_val), disabled=True, key=f"{key_prefix}_hr")
        st.text_input("Frequência (MHz)", value=str(freq_val), disabled=True, key=f"{key_prefix}_frq")

    with c2:
        st.text_input("Identificação", value=str(row.get("Identificação", "")), disabled=True, key=f"{key_prefix}_ident")
        st.text_input("Situação", value=str(row.get("Situação", "")), disabled=True, key=f"{key_prefix}_sit")
        st.text_input("Fiscal", value=str(row.get("Fiscal", "")), disabled=True, key=f"{key_prefix}_fisc")
        st.text_input("Processo SEI", value=str(row.get("Processo SEI UTE", row.get("Processo SEI ou Ato UTE", ""))), disabled=True, key=f"{key_prefix}_sei")
        st.text_input("ID", value=str(row.get("ID", "")), disabled=True, key=f"{key_prefix}_id")

    st.text_area("Observações/Ocorrência", value=str(obs_val), disabled=True, key=f"{key_prefix}_obs")

# ========================= TELAS =========================

def botao_voltar(label="⬅️ Voltar ao Menu", key=None):
    left, center, right = st.columns([2, 2, 2])
    with center:
        return st.button(label, use_container_width=True, key=key)

def tela_selecao_evento(client):
    """Tela inicial para escolha do evento (Planilha) - OTIMIZADA COM CALLBACK"""
    
    # --- CSS Centralização ---
    st.markdown(
        """
        <style>
            div[data-testid="stImage"] { display: flex; justify-content: center; }
            div[data-testid="stImage"] > img { width: 170px !important; }
        </style>
        """, 
        unsafe_allow_html=True
    )

    _, col_cent, _ = st.columns([1, 2, 1])
    
    with col_cent:
        img_b64 = _img_b64("anatel.png")
        if img_b64:
            st.markdown(
                f"""
                <div style="display: flex; justify-content: center;">
                    <img src="data:image/png;base64,{img_b64}" width="170">
                </div>
                """,
                unsafe_allow_html=True
            )
        
        st.markdown(f"<h3 style='text-align: center; color: #14337b;'>{TITULO_PRINCIPAL}</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Selecione o evento para carregar a base de dados:</p>", unsafe_allow_html=True)
        
        eventos_dict = buscar_planilhas(client)
        
        if not eventos_dict:
            st.error("Nenhuma planilha de 'Monitoração' encontrada.")
            # ... (seu código de erro continua igual aqui) ...
            return

        opcoes = list(eventos_dict.keys())
        
        # --- A MÁGICA DO CALLBACK ---
        # Definimos uma função interna que roda ANTES da interface ser atualizada
        def ao_selecionar():
            # Pega o valor da session_state usando a key definida no selectbox
            selecao = st.session_state.get("key_selecao_evento")
            if selecao:
                st.session_state['evento_nome'] = selecao
                st.session_state['spreadsheet_id'] = eventos_dict[selecao]
                st.session_state['view'] = 'main_menu'
                # O Streamlit fará o rerun automaticamente após este callback

        # O selectbox agora tem uma 'key' e um 'on_change'
        st.selectbox(
            "Eventos Disponíveis:", 
            opcoes, 
            index=None, 
            placeholder="Selecione...",
            key="key_selecao_evento",  # Identificador único
            on_change=ao_selecionar    # Chama a função acima IMEDIATAMENTE ao clicar
        )
        
        # NOTA: O bloco 'if escolha:' antigo foi removido, pois o 'on_change' cuida de tudo.

def tela_menu_principal(client, spread_id):
    render_header(show_logout=True)

    # --- LOADING ÚNICO E LIMPO ---
    # Tudo que estiver dentro do 'with st.spinner' será carregado enquanto mostra apenas uma msg
    with st.spinner("Carregando base de dados..."):
        df_painel = carregar_pendencias_painel_mapeadas(client, spread_id)
        df_abord  = carregar_pendencias_abordagem_pendentes(client, spread_id)
        df_estac  = carregar_pendencias_todas_estacoes(client, spread_id)
        
        # URL Dinâmica do Mapa (também consome tempo)
        link_mapa = get_city_map_url(client, spread_id)
    
    # Cálculos rápidos (não precisa de spinner)
    count_painel = len(df_painel) if df_painel is not None else 0
    count_abord = len(df_abord) if df_abord is not None else 0
    count_estac = len(df_estac) if df_estac is not None else 0
    total = count_painel + count_abord + count_estac

    label_tratar = f"**📝 TRATAR** emissões pendentes ({total})"
    
    # --- LAYOUT DOS BOTÕES ---
    _, button_col, _ = st.columns([1, 2, 1])
    
    with button_col:
        st.markdown('<div id="marker-vermelho"></div>', unsafe_allow_html=True)
        
        if st.button("**📋 INSERIR** emissão verificada em campo", use_container_width=True, key="btn_inserir"):
            st.session_state.view = 'inserir'; st.rerun()
            
        if st.button(label_tratar, use_container_width=True, key="btn_consultar"):
            st.session_state.view = 'consultar'; st.rerun()
            
        if st.button("**📵 REGISTRAR** Jammer ou ERB Fake", use_container_width=True, key="btn_bsr"):
            st.session_state.view = 'bsr_erb'; st.rerun()
            
        if st.button("**🔎 PESQUISAR** emissões cadastradas", use_container_width=True, key="btn_buscar"):
            st.session_state.view = 'busca'; st.rerun()
            
        if st.button("🗒️ **CONSULTAR** Atos de UTE", use_container_width=True, key="btn_ute"):
            st.session_state.view = 'tabela_ute'; st.rerun()
        
        # Botões de Links
        st.link_button("🗺️ **VER Mapa da Cidade**", link_mapa, use_container_width=True)
        st.link_button("🌍 **Tradutor de Voz**", "https://translate.google.com/?sl=auto&tl=pt&op=translate", use_container_width=True)

def tela_consultar(client, spread_id):
    render_header()
    st.markdown('<div class="info-green">Consulte as emissões pendentes de identificação.</div>', unsafe_allow_html=True)

    df_p = carregar_pendencias_painel_mapeadas(client, spread_id)
    df_a = carregar_pendencias_abordagem_pendentes(client, spread_id)
    df_e = carregar_pendencias_todas_estacoes(client, spread_id)
    
    # Concatena tudo
    dfs = [d for d in [df_p, df_a, df_e] if not d.empty]
    df_pend = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    if not df_pend.empty:
        opcoes = [f"{r['Local']} | {r['Data']} | {r['Frequência (MHz)']} MHz | {r.get('Ocorrência (observações)','')} | {r['ID']}" for _, r in df_pend.iterrows()]
        selecionado = st.selectbox("Selecione a emissão:", options=opcoes, index=None, placeholder="Escolha uma pendência...")

        if selecionado:
            idx = opcoes.index(selecionado)
            reg = df_pend.iloc[idx]
            
            st.markdown("#### Editar ocorrência")
            with st.form("form_editar_pendente"):
                c1, c2 = st.columns(2)
                
                # Coluna ESQUERDA (Somente Leitura)
                with c1:
                    st.text_input("ID", value=str(reg.get("ID","")), disabled=True)
                    st.text_input("Estação utilizada", value=str(reg.get("Local","")), disabled=True)
                    st.text_input("Fiscal", value=str(reg.get("Fiscal","")), disabled=True)
                    st.text_input("Data da identificação", value=str(reg.get("Data","")), disabled=True)
                    st.text_input("HH:mm", value=str(reg.get("HH:mm","") or reg.get("Hora","")), disabled=True)
                    st.text_input("Frequência (MHz)", value=str(reg.get("Frequência (MHz)","")), disabled=True)
                    st.text_input("Largura (kHz)", value=str(reg.get("Largura (kHz)","")), disabled=True)
                    st.text_input("Faixa de Frequência Envolvida", value=str(reg.get("Faixa de Frequência Envolvida","")), disabled=True)

                # Coluna DIREITA (Edição)
                with c2:
                    ident_v = str(reg.get("Identificação",""))
                    ident_edit = st.selectbox(f"Identificação {OBRIG}", IDENT_OPCOES, index=IDENT_OPCOES.index(ident_v) if ident_v in IDENT_OPCOES else 0)
                    
                    autz_v = str(reg.get("Autorizado?",""))
                    autz_opts = ["Sim", "Não", "Não licenciável"]
                    autz_edit = st.selectbox(f"Autorizado? {OBRIG}", autz_opts, index=autz_opts.index(autz_v) if autz_v in autz_opts else 2)
                    
                    ute_check = st.checkbox("UTE?", value=(str(reg.get("UTE?","")).lower() in ["sim","true","1","ok"]))
                    proc_edit = st.text_input("Processo SEI UTE (ou Ato UTE)", value=str(reg.get("Processo SEI UTE","")))
                    
                    obs_edit  = st.text_area("Ocorrência (observações)", value=str(reg.get("Ocorrência (observações)","")))
                    
                    cient_edit = st.text_input("Alguém mais ciente?", value=str(reg.get("Alguém mais ciente?","")))

                    interf_v = str(reg.get("Interferente?",""))
                    interf_opts = ["Sim", "Não", "Indefinido"]
                    interf_edit = st.selectbox(f"Interferente? {OBRIG}", interf_opts, index=interf_opts.index(interf_v) if interf_v in interf_opts else 2)
                    
                    situ_v = str(reg.get("Situação","Pendente"))
                    situ_opts = ["Pendente", "Concluído"]
                    situ_edit = st.selectbox(f"Situação {OBRIG}", situ_opts, index=situ_opts.index(situ_v) if situ_v in situ_opts else 0)

                if st.form_submit_button("Salvar alterações", use_container_width=True):
                    erros = []
                    if not ident_edit: erros.append("Identificação")
                    if ute_check and not proc_edit: erros.append("Processo SEI (UTE)")
                    
                    if erros: st.error("Faltam dados: " + ", ".join(erros))
                    else:
                        pac = {
                            "Identificação": ident_edit, "Autorizado?": autz_edit, 
                            "UTE?": "Sim" if ute_check else "Não", "Processo SEI UTE": proc_edit,
                            "Ocorrência (observações)": obs_edit, 
                            "Alguém mais ciente?": cient_edit,
                            "Interferente?": interf_edit, "Situação": situ_edit
                        }
                        # PAINEL ou ESTACAO usam a mesma lógica de atualização
                        if reg["Fonte"] == "PAINEL" or reg["Fonte"] == "ESTACAO":
                            res = atualizar_campos_na_aba_mae(client, spread_id, str(reg["EstacaoRaw"]), str(reg["ID"]), pac)
                        else:
                            res = atualizar_campos_abordagem_por_id(client, spread_id, str(reg["ID"]), pac)
                        
                        st.success(res)
    else:
        st.success("✔️ Nenhuma pendência encontrada.")

    if botao_voltar(): st.session_state.view = 'main_menu'; st.rerun()

def tela_inserir(client, spread_id):
    render_header()

    # --- CSS: BOTÕES COLORIDOS + REMOÇÃO DE +/- EM NUMBERS ---
    st.markdown("""
    <style>
    /* 1. ESTILO DO BOTÃO DE REGISTRAR (Azul -> Verde no Hover) */
    div[data-testid="stForm"] button {
        background: linear-gradient(to bottom, #14337b, #4464A7) !important;
        border: 3.4px solid #54515c !important;
        border-radius: 8px !important;
        color: white !important;
        font-weight: 600 !important;
        font-size: 1.02em !important;
        height: 3.8em !important;
        box-shadow: 2px 2px 5px rgba(0,0,0,.3) !important;
        transition: all 0.2s ease-in-out !important;
    }
    div[data-testid="stForm"] button:hover {
        background: linear-gradient(to bottom, #9ccc65, #AED581) !important;
        border-color: #7cb342 !important;
        color: white !important;
        transform: scale(1.02);
        box-shadow: 0px 4px 15px rgba(0,0,0,0.2) !important;
    }
    div[data-testid="stForm"] button:active, 
    div[data-testid="stForm"] button:focus {
        background: linear-gradient(to bottom, #7cb342, #9ccc65) !important;
        border-color: #558b2f !important;
        color: white !important;
    }

    /* 2. REMOVER OS BOTÕES + E - DOS CAMPOS NUMÉRICOS (Frequência/Largura) */
    div[data-testid="stNumberInput"] button {
        display: none !important;
    }
    /* Ajuste fino para evitar buraco onde ficavam os botões */
    div[data-testid="stNumberInput"] > div {
        border-right: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Lógica de Confirmação de Frequência ---
    if st.session_state.get('confirm_freq_asked', False):
        dados = st.session_state.get('dados_para_salvar', {})
        regiao = st.session_state.get('regiao_existente', 'Desconhecida')
        st.markdown(f"<div class='confirm-warning'>ATENÇÃO: Frequência <strong>{dados.get('Frequência em MHz')} MHz</strong> já existe em <strong>{regiao}</strong>.<br>Registrar mesmo assim?</div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        if c1.button("Sim, Registrar"):
            inserir_emissao_I_W(client, spread_id, dados)
            st.session_state.insert_success = "Emissão registrada com sucesso!"
            del st.session_state.confirm_freq_asked
            st.rerun()
        if c2.button("Não, Cancelar"):
            del st.session_state.confirm_freq_asked
            st.info("Registro cancelado.")
            st.rerun()
        return

    # --- FORMULÁRIO ---
    freqs_map = carregar_todas_frequencias(client, spread_id)
    idents = carregar_opcoes_identificacao(client, spread_id)
    
    dados_prev = st.session_state.get('dados_para_salvar', {})
    
    with st.form("form_nova_emissao"):
        col1, col2 = st.columns(2)
        val_dia = dados_prev.get('Dia', datetime.now(ZoneInfo("America/Sao_Paulo")).date())
        val_hora = dados_prev.get('Hora', datetime.now(ZoneInfo("America/Sao_Paulo")).time())
        
        dia = col1.date_input(f"Data {OBRIG}", value=val_dia, format="DD/MM/YYYY")
        hora = col2.time_input(f"Hora {OBRIG}", value=val_hora)
        fiscal = st.text_input(f"Fiscal {OBRIG}", value=dados_prev.get('Fiscal', ''))
        local = st.text_input("Local/Região", value=dados_prev.get('Local/Região', ''))
        
        c3, c4 = st.columns(2)
        # step=0.0 ou step=None não removem os botões nativamente, por isso usamos o CSS acima
        freq = c3.number_input(f"Frequência (MHz) {OBRIG}", value=dados_prev.get('Frequência em MHz', 0.0), format="%.3f")
        larg = c4.number_input(f"Largura (kHz) {OBRIG}", value=dados_prev.get('Largura em kHz', 0.0), format="%.1f")
        
        faixa = st.selectbox(f"Faixa relacionada {OBRIG}", FAIXA_OPCOES, index=None, placeholder="Selecione...")
        ident = st.selectbox(f"Identificação {OBRIG}", idents, index=None, placeholder="Selecione...")
        
        ute = st.checkbox("UTE?", value=dados_prev.get('UTE?', False))
        proc = st.text_input("Processo SEI UTE", value=dados_prev.get('Processo SEI ou Ato UTE', ''))
        obs = st.text_area(f"Entidade Resp./Contato/Observações {OBRIG}", value=dados_prev.get('Observações/Detalhes/Contatos', ''))
        
        situ_opts = ["Pendente", "Concluído"]
        situacao = st.selectbox(f"Status desta emissão {OBRIG}", situ_opts, index=None, placeholder="Selecione o status")
        
        st.write("") 

        # AVISO DE SUCESSO LOGO ACIMA DO BOTÃO
        if 'insert_success' in st.session_state:
            st.success(st.session_state.insert_success)
            del st.session_state.insert_success

        submitted = st.form_submit_button("Registrar Emissão", use_container_width=True)

        if submitted:
            erros = []
            if not fiscal: erros.append("Fiscal")
            if freq <= 0: erros.append("Frequência")
            if larg <= 0: erros.append("Largura")
            if not faixa: erros.append("Faixa")
            if not ident: erros.append("Identificação")
            if not obs: erros.append("Observações")
            if ute and not proc: erros.append("Processo SEI")
            if not situacao: erros.append("Status desta emissão")
            
            if erros: st.error("Preencha: " + ", ".join(erros))
            else:
                dados_submit = {
                    'Dia': dia, 'Hora': hora, 'Fiscal': fiscal, 'Local/Região': local,
                    'Frequência em MHz': freq, 'Largura em kHz': larg, 'Faixa de Frequência': faixa,
                    'Identificação': ident, 'UTE?': ute, 'Processo SEI ou Ato UTE': proc,
                    'Observações/Detalhes/Contatos': obs, 'Situação': situacao,
                    'Autorizado? (Q)': 'Indefinido', 'Interferente?': 'Indefinido'
                }
                st.session_state.dados_para_salvar = dados_submit
                
                # Check Duplicidade
                f_check = round(float(freq), 3)
                if f_check in freqs_map:
                    st.session_state.confirm_freq_asked = True
                    st.session_state.regiao_existente = freqs_map[f_check]
                    st.rerun()
                else:
                    if inserir_emissao_I_W(client, spread_id, dados_submit):
                        st.session_state.insert_success = "Emissão inserida com sucesso. Caso queira continuar inserindo emissões desta entidade, basta alterar os dados específicos e clicar em Registrar Emissão"
                        if 'dados_para_salvar' in st.session_state:
                            del st.session_state['dados_para_salvar']
                        st.rerun()

    if botao_voltar(): st.session_state.view = 'main_menu'; st.rerun()

def tela_bsr_erb(client, spread_id):
    render_header()
    
    st.markdown('<div id="marker-bsr-erb-form"></div>', unsafe_allow_html=True)
    with st.form("form_bsr"):
        tipo = st.radio(f"Tipo {OBRIG}", ('BSR/Jammer', 'ERB Fake'))
        regiao = st.text_input(f"Local {OBRIG}")
        lat = st.text_input("Latitude (-N.NNNN)")
        lon = st.text_input("Longitude (-N.NNNN)")
        
        if st.form_submit_button("Registrar", use_container_width=True):
            if not regiao: st.error("Local obrigatório")
            elif not _valid_neg_coord(lat) or not _valid_neg_coord(lon): st.error("Coords inválidas")
            else:
                res = inserir_bsr_erb(client, spread_id, tipo, regiao, lat, lon)
                st.success(res)

    if botao_voltar(): st.session_state.view = 'main_menu'; st.rerun()

def tela_busca(client, spread_id):
    render_header()
    
    termo = st.text_input("Buscar texto (mín 3 chars):")
    
    # Abas dinâmicas
    abas_est = listar_abas_estacoes(client, spread_id)
    
    # --- ALTERAÇÃO: Removido "PAINEL" da lista. Fica apenas Abordagem + Estações ---
    abas_ops = ["Abordagem"] + abas_est
    
    abas_sel = st.multiselect("Abas:", abas_ops, default=abas_ops)
    
    if st.button("Consultar", use_container_width=True):
        termo_clean = termo.strip()
        if len(termo_clean) < 3: 
            st.warning("Digite pelo menos 3 caracteres para consultar.")
        else:
            with st.spinner("Buscando..."):
                res = _buscar_por_texto_livre(client, spread_id, termo_clean, abas_sel)
            
            if res.empty: 
                st.info("Nenhum resultado encontrado.")
            else:
                st.success(f"Resultados encontrados: {len(res)}")
                
                for i, (_, row) in enumerate(res.iterrows(), start=1):
                    # --- LÓGICA DE CONSTRUÇÃO DO CABEÇALHO ---
                    cabecalho = []
                    aba_origem = row.get("Aba/Origem", "")
                    
                    # Tenta pegar Localização
                    loc = row.get("Local", row.get("Local/Região", row.get("Estação", "")))
                    if not loc and aba_origem: loc = aba_origem
                    if loc: cabecalho.append(str(loc))
                    
                    # Tenta pegar Data
                    dt = row.get("Data", row.get("Dia", ""))
                    if dt: cabecalho.append(str(dt))
                    
                    # Tenta pegar Frequência
                    fr = row.get("Frequência (MHz)", row.get("Frequência", ""))
                    if fr: cabecalho.append(f"{fr} MHz")
                    
                    # ID
                    id_val = row.get("ID", "")
                    if id_val: cabecalho.append(f"ID {id_val}")
                    
                    titulo_expander = " | ".join(cabecalho) if cabecalho else f"Resultado #{i}"

                    with st.expander(titulo_expander):
                        # Gera um prefixo único para os widgets não conflitarem
                        key_prefix = f"busca_{i}_{id_val}"
                        render_ocorrencia_readonly(row, key_prefix=key_prefix)

    if botao_voltar(key="voltar_busca"): 
        st.session_state.view = 'main_menu'
        st.rerun()

def tela_tabela_ute(client, spread_id):
    render_header()
    
    # --- REMOVIDO st.divider() PARA EVITAR DUPLICIDADE ---
    
    # Título
    evento_atual = st.session_state.get('evento_nome', 'Evento')
    st.markdown(f"#### Atos de UTE - {evento_atual}") 
    
    # Aviso de girar celular
    st.markdown(
        "<p style='text-align: center; font-size: small; margin-top: -0.5rem; margin-bottom: 0.5rem; color: #555;'>(gire o celular ⟳)</p>", 
        unsafe_allow_html=True
    )
    
    # JavaScript para copiar (Mantido)
    st.markdown("""
    <script>
    function copyToClipboard(text, element) {
        const el = document.createElement('textarea');
        el.value = text;
        el.style.position = 'absolute';
        el.style.left = '-9999px';
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        element.innerHTML = 'Copiado!';
        setTimeout(() => { element.innerHTML = text; }, 1500);
    }
    </script>
    """, unsafe_allow_html=True)
    
    df = carregar_dados_ute(client, spread_id)
    if not df.empty:
        html = "<table class='ute-table'><thead><tr><th>País/Entidade</th><th>Freq (MHz)</th><th>BW (kHz)</th><th>Processo SEI</th></tr></thead><tbody>"
        for _, row in df.iterrows():
            proc = str(row['Processo SEI'])
            html += f"<tr><td>{row['País/Entidade']}</td><td>{row['Frequência (MHz)']}</td><td>{row['Largura (kHz)']}</td>"
            html += f"<td class='copyable-cell' onclick='copyToClipboard(\"{proc}\", this)'>{proc}</td></tr>"
        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.info("Sem dados de UTE.")
    
    c1, c2 = st.columns(2)
    c1.link_button("SEI Interno", "https://sei.anatel.gov.br", use_container_width=True)
    c2.link_button("SEI Público", "https://sei.anatel.gov.br/sei/modulos/pesquisa/md_pesq_processo_pesquisar.php?acao_externa=protocolo_pesquisar&acao_origem_externa=protocolo_pesquisar&id_orgao_acesso_externo=0", use_container_width=True)
    
    if botao_voltar(): st.session_state.view = 'main_menu'; st.rerun()

# =========================== MAIN ===========================
try:
    client_g = obter_cliente_gspread()
    
    # Inicializa estados
    if 'view' not in st.session_state: st.session_state.view = 'selecao'
    if 'spreadsheet_id' not in st.session_state: st.session_state.spreadsheet_id = None

    # Roteamento
    if st.session_state.view == 'selecao' or not st.session_state.spreadsheet_id:
        tela_selecao_evento(client_g)
    else:
        sp_id = st.session_state.spreadsheet_id
        # Passa o cliente para todas as telas se necessário
        if st.session_state.view == 'main_menu': tela_menu_principal(client_g, sp_id)
        elif st.session_state.view == 'consultar': tela_consultar(client_g, sp_id)
        elif st.session_state.view == 'inserir': tela_inserir(client_g, sp_id)
        elif st.session_state.view == 'bsr_erb': tela_bsr_erb(client_g, sp_id)
        elif st.session_state.view == 'busca': tela_busca(client_g, sp_id)
        elif st.session_state.view == 'tabela_ute': tela_tabela_ute(client_g, sp_id)

except Exception as e:
    st.error("Erro fatal na aplicação.")
    st.exception(e)