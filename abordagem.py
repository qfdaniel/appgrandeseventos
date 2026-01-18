# -*- coding: utf-8 -*-
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
BTN_HEIGHT = "5.12em"   # Altura de TODOS os botões
BTN_GAP    = "3px"      # Espaçamento vertical unificado
ABAS_SISTEMA = ["PAINEL", "Abordagem", "Tabela UTE", "Escala", "LISTAS"] 
# ============================================================

# --- CONFIG DA PÁGINA ---
st.set_page_config(
    page_title="App Grandes Eventos",
    page_icon="anatel.png",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CONSTANTES ---
TITULO_PRINCIPAL = "App Grandes Eventos"
OBRIG = ":red[**\\***]"

# --- MAPA DINÂMICO ---
def get_maps_url(evento_nome):
    """Retorna URL do Maps centrada na cidade do evento"""
    nome = (evento_nome or "").lower()
    if "rj" in nome or "rio" in nome: return "https://www.google.com/maps/@-22.9068,-43.1729,12z"
    if "ba" in nome or "salvador" in nome: return "https://www.google.com/maps/@-12.9777,-38.5016,12z"
    if "sp" in nome or "paulo" in nome: return "https://www.google.com/maps/@-23.5505,-46.6333,12z"
    if "belem" in nome or "belém" in nome or "cop" in nome: return "https://www.google.com/maps/@-1.4558,-48.4902,12z"
    if "recife" in nome: return "https://www.google.com/maps/@-8.0476,-34.8770,12z"
    if "manaus" in nome: return "https://www.google.com/maps/@-3.1190,-60.0217,12z"
    if "brasilia" in nome or "df" in nome: return "https://www.google.com/maps/@-15.7975,-47.8919,12z"
    # Fallback genérico
    return "https://www.google.com/maps/d/u/0/edit?mid=1E7uIgoEchrY_KQn4jzu4ePs8WrdWwxc&usp=sharing"

IDENT_OPCOES = [
    "Sinal de dados", "Comunicação (voz) relacionada ao evento", "Comunicação (voz) não relacionada ao evento",
    "Sinal não relacionado ao evento", "Espúrio ou Produto de Intermodulação", "Ruído", "Não identificado",
]

FAIXA_OPCOES = ["FM", "SMA", "SMM", "SLP", "TV", "SMP", "GNSS", "Satélite", "Radiação Restrita"]

# --- CONEXÃO GSPREAD ---
@st.cache_resource(ttl=3600)
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

def render_header(imagem: str = "anatel.png"):
    img_b64 = _img_b64(imagem)
    img_tag = f'<img class="hdr-img" src="data:image/png;base64,{img_b64}" alt="Logo Anatel">' if img_b64 else ""
    
    evento_atual = st.session_state.get('evento_nome', '')
    
    # Texto do subtítulo
    texto_display = f"Evento selecionado: {evento_atual}" if evento_atual else ""
    subtitulo = f"<h4 style='color:#2E7D32; margin:0; font-size: 0.90rem; margin-top: -12px; font-weight: 600; letter-spacing: -0.3px;'>{texto_display}</h4>" if texto_display else ""

    # Estrutura do Header
    st.markdown(
        f"""
        <div class="header-logos">
            <div class="hdr-left">{img_tag}</div>
            <div class="hdr-center">
                <h2>{TITULO_PRINCIPAL}</h2>
                {subtitulo}
            </div>
            <div class="hdr-right"></div>
        </div>
        """,
        unsafe_allow_html=True
    )

# --- CSS ---
st.markdown(f"""
<style>
  :root{{ --btn-height: {BTN_HEIGHT}; --btn-gap: {BTN_GAP}; --btn-font: 1.02em; }}
  .block-container {{ max-width: 760px; padding-top: .45rem; padding-bottom: .55rem; margin: 0 auto; }}
  .stApp {{ background-color: #F1F8E9; }}
  
  #MainMenu, footer, header {{ visibility: hidden; }}
  div[data-testid="stHorizontalBlock"] {{ gap: 0rem !important; }}
  div[data-testid="stWidgetLabel"] > label {{ color:#000 !important; text-shadow: 0 1px 0 rgba(0,0,0,.05); }}
  
  /* --- HEADER AJUSTADO --- */
  .header-logos {{
    display: grid; 
    grid-template-columns: 70px 1fr 70px;
    align-items: center; 
    text-align: center; 
    margin-bottom: -8px;
    padding: 0 5px;
  }}
  
  .hdr-img {{ height: 46px; }} 
  .hdr-left {{ justify-self: end; display: flex; align-items: center; padding-right: 5px; }}
  .hdr-center {{ justify-self: center; width: 100%; }}
  .hdr-right {{ justify-self: start; }}
  
  .header-logos h2{{
    margin:0; color:#1A311F; font-weight:800;
    text-shadow: 1px 1px 0 rgba(255,255,255,.35), 0 1px 2px rgba(0,0,0,.28);
    font-size: 1.6rem;
    line-height: 1.1;
    margin-bottom: 0px;
  }}

  hr {{ margin-top: 0 !important; margin-bottom: 1rem !important; }}

  /* Botões */
  .stButton > button, .app-btn, div[data-testid="stLinkButton"] a {{
    width:100%; height: var(--btn-height); min-height: var(--btn-height);
    font-size: var(--btn-font) !important; font-weight:600 !important;
    border-radius:8px !important; border: 3.4px solid #54515c !important;
    color: white !important; background: linear-gradient(to bottom, #14337b, #4464A7) !important;
    box-shadow: 2px 2px 5px rgba(0,0,0,.3) !important;
    margin: 0 0 var(--btn-gap) 0 !important;
    display: flex; align-items: center; justify-content: center;
    text-decoration: none !important;
  }}
  .stButton > button:hover, div[data-testid="stLinkButton"] a:hover {{ 
    filter: brightness(1.03) !important; transform: translateY(-2px) !important; 
  }}

  /* Botões Vermelhos */
  #marker-vermelho {{ display: none; }}
  div[data-testid="stElementContainer"]:has(#marker-vermelho) ~ div[data-testid="stElementContainer"]:nth-of-type(-n+4) .stButton > button {{
    background: linear-gradient(to bottom, #c62828, #e53935) !important; border-color: #a92222 !important;
  }}
  
  /* Botões Verdes */
  div[data-testid="stLinkButton"] a[href*="translate.google.com"],
  div[data-testid="stLinkButton"] a[href*="http://googleusercontent.com/maps.google.com"] {{
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

def _normalize_text(s: str) -> str:
    if s is None: return ""
    s = str(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.strip().lower()

@st.cache_data(ttl=180)
def listar_abas_estacoes(_client, spreadsheet_id):
    try:
        planilha = abrir_planilha_selecionada(_client, spreadsheet_id)
        todas = [ws.title for ws in planilha.worksheets()]
        estacoes = [t for t in todas if t not in ABAS_SISTEMA]
        return estacoes
    except:
        return []

# ===================== FUNÇÕES DE CARGA =====================

@st.cache_data(ttl=180)
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
                    "País": row[0], "Frequência (MHz)": row[4],
                    "Largura (kHz)": row[5], "Processo SEI": row[7]
                })
        df = pd.DataFrame(dados)
        df = df[df["Processo SEI"].str.strip() != ""]
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=180)
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

@st.cache_data(ttl=180)
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
            "HH:mm": "",
            "Frequência (MHz)": get_col(5), # M
            "Largura (kHz)": get_col(6),    # N
            "Faixa de Frequência Envolvida": get_col(7), # O
            "Identificação": "",
            "Autorizado?": "", "UTE?": "", "Processo SEI UTE": "",
            "Ocorrência (observações)": get_col(12), # T
            "Alguém mais ciente?": "",
            "Interferente?": get_col(14), # V
            "Situação": get_col(15),      # W
            "Fonte": "ABORDAGEM",
        })

        pend = pend[pend["Situação"].str.strip().str.lower().eq("pendente")].copy()
        pend = pend.sort_values(by=["Local","Data"], kind="stable").reset_index(drop=True)
        return pend
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=180)
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
            "Interferente?": "V", "Situação": "W"
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

@st.cache_data(ttl=3600)
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

# ========================= TELAS =========================

def botao_voltar(label="⬅️ Voltar ao Menu", key=None):
    left, center, right = st.columns([2, 2, 2])
    with center:
        return st.button(label, use_container_width=True, key=key)

def tela_selecao_evento(client):
    """Tela inicial para escolha do evento (Planilha)"""
    
    # CSS para centralizar a imagem gerada pelo st.image apenas nesta tela
    st.markdown(
        """
        <style>
            div[data-testid="stImage"] {
                display: flex;
                justify-content: center;
            }
            div[data-testid="stImage"] > img {
                width: 170px !important;
            }
        </style>
        """, 
        unsafe_allow_html=True
    )

    # Layout de colunas para centralizar
    _, col_cent, _ = st.columns([1, 2, 1])
    
    with col_cent:
        # Imagem reduzida em 15% (de 200px para 170px)
        st.image("anatel.png", width=170)
        
        st.markdown(f"<h3 style='text-align: center; color: #14337b;'>{TITULO_PRINCIPAL}</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Selecione o evento para carregar a base de dados:</p>", unsafe_allow_html=True)
        
        eventos_dict = buscar_planilhas(client)
        
        if not eventos_dict:
            st.error("Nenhuma planilha de 'Monitoração' encontrada.")
            return

        opcoes = ["Selecione..."] + list(eventos_dict.keys())
        escolha = st.selectbox("Eventos Disponíveis:", opcoes)

        # --- PULO AUTOMÁTICO ---
        if escolha != "Selecione...":
            st.session_state['evento_nome'] = escolha
            st.session_state['spreadsheet_id'] = eventos_dict[escolha]
            st.session_state['view'] = 'main_menu'
            st.rerun()

def tela_menu_principal(client, spread_id):
    render_header()
    st.divider()

    df_painel = carregar_pendencias_painel_mapeadas(client, spread_id)
    df_abord  = carregar_pendencias_abordagem_pendentes(client, spread_id)
    
    count_painel = len(df_painel) if df_painel is not None else 0
    count_abord = len(df_abord) if df_abord is not None else 0
    total = count_painel + count_abord

    label_tratar = f"**📝 TRATAR** emissões pendentes ({total})"
    
    # URL Dinâmica do Mapa
    cidade_atual = st.session_state.get('evento_nome', '')
    link_mapa = get_maps_url(cidade_atual)

    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        _, button_col, _ = st.columns([0.5, 9, 0.5])
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
            
            st.link_button("🗺️ **Mapa das Estações**", link_mapa, use_container_width=True)
            st.link_button("🌍 **Tradutor de Voz**", "https://translate.google.com/?sl=auto&tl=pt&op=translate", use_container_width=True)
            
            st.markdown("---")
            if st.button("🔄 Trocar Evento", use_container_width=True):
                for key in ['evento_nome', 'spreadsheet_id']:
                    if key in st.session_state: del st.session_state[key]
                st.session_state.view = 'selecao'
                st.rerun()

def tela_consultar(client, spread_id):
    render_header()
    st.divider()
    st.markdown('<div class="info-green">Consulte as emissões pendentes de identificação.</div>', unsafe_allow_html=True)

    df_p = carregar_pendencias_painel_mapeadas(client, spread_id)
    df_a = carregar_pendencias_abordagem_pendentes(client, spread_id)
    df_pend = pd.concat([df_p, df_a], ignore_index=True) if (not df_p.empty and not df_a.empty) else (df_p if not df_p.empty else df_a)

    if not df_pend.empty:
        opcoes = [f"{r['Local']} | {r['Data']} | {r['Frequência (MHz)']} MHz | {r.get('Ocorrência (observações)','')} | {r['ID']}" for _, r in df_pend.iterrows()]
        selecionado = st.selectbox("Selecione a emissão:", options=opcoes, index=None, placeholder="Escolha uma pendência...")

        if selecionado:
            idx = opcoes.index(selecionado)
            reg = df_pend.iloc[idx]
            
            st.markdown("#### Editar ocorrência")
            with st.form("form_editar_pendente"):
                c1, c2 = st.columns(2)
                with c1:
                    st.text_input("ID", value=str(reg.get("ID","")), disabled=True)
                    st.text_input("Estação", value=str(reg.get("Local","")), disabled=True)
                    st.text_input("Freq (MHz)", value=str(reg.get("Frequência (MHz)","")), disabled=True)
                with c2:
                    ident_v = str(reg.get("Identificação",""))
                    ident_edit = st.selectbox(f"Identificação {OBRIG}", IDENT_OPCOES, index=IDENT_OPCOES.index(ident_v) if ident_v in IDENT_OPCOES else 0)
                    
                    autz_v = str(reg.get("Autorizado?",""))
                    autz_opts = ["Sim", "Não", "Não licenciável"]
                    autz_edit = st.selectbox(f"Autorizado? {OBRIG}", autz_opts, index=autz_opts.index(autz_v) if autz_v in autz_opts else 2)
                    
                    ute_check = st.checkbox("UTE?", value=(str(reg.get("UTE?","")).lower() in ["sim","true","1","ok"]))
                    proc_edit = st.text_input("Processo SEI UTE", value=str(reg.get("Processo SEI UTE","")))
                    obs_edit  = st.text_area("Observações", value=str(reg.get("Ocorrência (observações)","")))
                    
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
                            "Ocorrência (observações)": obs_edit, "Interferente?": interf_edit, "Situação": situ_edit
                        }
                        if reg["Fonte"] == "PAINEL":
                            res = atualizar_campos_na_aba_mae(client, spread_id, str(reg["EstacaoRaw"]), str(reg["ID"]), pac)
                        else:
                            res = atualizar_campos_abordagem_por_id(client, spread_id, str(reg["ID"]), pac)
                        
                        st.success(res)
    else:
        st.success("✔️ Nenhuma pendência encontrada.")

    if botao_voltar(): st.session_state.view = 'main_menu'; st.rerun()

def tela_inserir(client, spread_id):
    render_header()
    st.divider()

    # --- ESTADOS DA TELA ---
    if 'insert_success' in st.session_state:
        st.success(st.session_state.insert_success)
        del st.session_state.insert_success

    if st.session_state.get('confirm_freq_asked', False):
        dados = st.session_state.get('dados_para_salvar', {})
        regiao = st.session_state.get('regiao_existente', 'Desconhecida')
        st.markdown(f"<div class='confirm-warning'>ATENÇÃO: Frequência <strong>{dados.get('Frequência em MHz')} MHz</strong> já existe em <strong>{regiao}</strong>.<br>Registrar mesmo assim?</div>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        if c1.button("Sim, Registrar"):
            inserir_emissao_I_W(client, spread_id, dados)
            st.session_state.insert_success = "Emissão registrada!"
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
        
        dia = col1.date_input(f"Data {OBRIG}", value=val_dia)
        hora = col2.time_input(f"Hora {OBRIG}", value=val_hora)
        fiscal = st.text_input(f"Fiscal {OBRIG}", value=dados_prev.get('Fiscal', ''))
        local = st.text_input("Local/Região", value=dados_prev.get('Local/Região', ''))
        
        c3, c4 = st.columns(2)
        freq = c3.number_input(f"Frequência (MHz) {OBRIG}", value=dados_prev.get('Frequência em MHz', 0.0), format="%.3f")
        larg = c4.number_input(f"Largura (kHz) {OBRIG}", value=dados_prev.get('Largura em kHz', 0.0), format="%.1f")
        
        faixa = st.selectbox(f"Faixa {OBRIG}", FAIXA_OPCOES, index=None, placeholder="Selecione...")
        ident = st.selectbox(f"Identificação {OBRIG}", idents, index=None, placeholder="Selecione...")
        
        ute = st.checkbox("UTE?", value=dados_prev.get('UTE?', False))
        proc = st.text_input("Processo SEI UTE", value=dados_prev.get('Processo SEI ou Ato UTE', ''))
        obs = st.text_area(f"Observações {OBRIG}", value=dados_prev.get('Observações/Detalhes/Contatos', ''))
        
        submitted = st.form_submit_button("Registrar Emissão", use_container_width=True)

        if submitted:
            erros = []
            if not fiscal: erros.append("Fiscal")
            if freq <= 0: erros.append("Frequência")
            if not faixa: erros.append("Faixa")
            if not ident: erros.append("Identificação")
            if not obs: erros.append("Observações")
            if ute and not proc: erros.append("Processo SEI")
            
            if erros: st.error("Preencha: " + ", ".join(erros))
            else:
                dados_submit = {
                    'Dia': dia, 'Hora': hora, 'Fiscal': fiscal, 'Local/Região': local,
                    'Frequência em MHz': freq, 'Largura em kHz': larg, 'Faixa de Frequência': faixa,
                    'Identificação': ident, 'UTE?': ute, 'Processo SEI ou Ato UTE': proc,
                    'Observações/Detalhes/Contatos': obs, 'Situação': 'Pendente',
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
                        st.session_state.insert_success = "Sucesso!"
                        st.rerun()

    if botao_voltar(): st.session_state.view = 'main_menu'; st.rerun()

def tela_bsr_erb(client, spread_id):
    render_header()
    st.divider()
    
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
    st.divider()
    
    termo = st.text_input("Buscar texto (mín 3 chars):")
    
    # Abas dinâmicas
    abas_est = listar_abas_estacoes(client, spread_id)
    abas_ops = ["PAINEL", "Abordagem"] + abas_est
    abas_sel = st.multiselect("Abas:", abas_ops, default=abas_ops)
    
    if st.button("Consultar", use_container_width=True):
        if len(termo) < 3: st.warning("Texto muito curto")
        else:
            with st.spinner("Buscando..."):
                res = _buscar_por_texto_livre(client, spread_id, termo, abas_sel)
            if res.empty: st.info("Nada encontrado.")
            else:
                st.success(f"{len(res)} resultados.")
                for i, r in res.iterrows():
                    with st.expander(f"{r.get('Aba/Origem')} | {r.get('Frequência (MHz)', '')} MHz | {r.get('Data','')}"):
                        st.json(r.to_dict())

    if botao_voltar(): st.session_state.view = 'main_menu'; st.rerun()

def tela_tabela_ute(client, spread_id):
    render_header()
    st.divider()
    
    # JavaScript para copiar
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
        html = "<table class='ute-table'><thead><tr><th>País</th><th>Freq (MHz)</th><th>BW (kHz)</th><th>Processo SEI</th></tr></thead><tbody>"
        for _, row in df.iterrows():
            proc = str(row['Processo SEI'])
            html += f"<tr><td>{row['País']}</td><td>{row['Frequência (MHz)']}</td><td>{row['Largura (kHz)']}</td>"
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
        if st.session_state.view == 'main_menu': tela_menu_principal(client_g, sp_id)
        elif st.session_state.view == 'consultar': tela_consultar(client_g, sp_id)
        elif st.session_state.view == 'inserir': tela_inserir(client_g, sp_id)
        elif st.session_state.view == 'bsr_erb': tela_bsr_erb(client_g, sp_id)
        elif st.session_state.view == 'busca': tela_busca(client_g, sp_id)
        elif st.session_state.view == 'tabela_ute': tela_tabela_ute(client_g, sp_id)

except Exception as e:
    st.error("Erro fatal na aplicação.")
    st.exception(e)