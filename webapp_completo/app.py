import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# =========================================================================
# CONFIGURAÇÃO DE ESTÉTICA E PÁGINA (ESTILO TERMINAL BLOOMBERG)
# =========================================================================
st.set_page_config(
    page_title="Terminal Tributário - Modelo Algorítmico",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Injetando CSS customizado para o tema executivo moderno
st.markdown("""
    <style>
    /* Fundo geral aplicado caso o config.toml não sobreponha 100% */
    .stApp {
        background-color: #141518;
        color: #E0E0E0;
        font-family: 'Inter', 'Roboto', sans-serif;
    }
    
    /* Fundo dos containers com borda (cards) para um tom acima do fundo */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #262730;
        border-radius: 8px;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #262730;
        border-right: 1px solid #3A3B45;
    }
    
    /* Headers e textos de destaque em Dourado */
    h1, h2, h3, h4, h5, h6 {
        color: #E5C158 !important; /* Dourado suave/brilhante */
        font-family: 'Inter', 'Roboto', sans-serif !important;
    }
    
    /* Estilo das métricas (valores) em Verde Neon */
    [data-testid="stMetricValue"] {
        color: #4ADE80 !important; /* Verde vibrante */
    }
    
    /* Estilo das métricas (títulos) em Cinza Claro */
    [data-testid="stMetricLabel"] {
        color: #A0AEC0 !important; /* Cinza claro */
    }
    
    /* Ajustes nas tabs e outros elementos */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        white-space: pre-wrap;
        background-color: #262730;
        border-radius: 8px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
        padding-left: 16px;
        padding-right: 16px;
        border: none;
        color: #A0AEC0;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        color: #4C97FF !important;
        border-bottom: 2px solid #4C97FF !important;
        border-radius: 0px !important;
    }
    </style>
""", unsafe_allow_html=True)


# =========================================================================
# FUNÇÕES MATEMÁTICAS EXATAS DOS NOTEBOOKS
# =========================================================================
@st.cache_data(show_spinner="Gerando Base Sintética de Imóveis (Monte Carlo)...")
def gerar_base_imobiliaria(
    n_linhas=3000000, 
    concentracao_fundiaria=1.5, 
    media_metragem=95.0, 
    std_metragem=100.0,
    usar_preco_m2=True, 
    media_preco_m2=8000.0, 
    std_preco_m2=7000.0,
    media_valor_indep=500000.0, 
    std_valor_indep=150000.0,
    taxa_ocupacao_mercado=0.85,
    taxa_aluguel_mensal=0.005,
    variancia_aluguel_std=0.15
):
    n_cpfs_unicos = int(n_linhas * 0.6)
    pesos_patrimonio = np.random.lognormal(mean=0, sigma=concentracao_fundiaria, size=n_cpfs_unicos)
    probabilidades = pesos_patrimonio / pesos_patrimonio.sum()
    
    cpfs_brutos = np.random.choice(np.arange(1, n_cpfs_unicos + 1), size=n_linhas, p=probabilidades)
    df = pd.DataFrame({'CPF_ID': cpfs_brutos})
    df['CPF'] = "CPF_" + df['CPF_ID'].astype(str).str.zfill(7)
    
    df['Metragem'] = np.random.normal(loc=media_metragem, scale=std_metragem, size=n_linhas)
    df['Metragem'] = np.clip(df['Metragem'], a_min=15.0, a_max=None).round(2)
    
    if usar_preco_m2:
        preco_m2_vetor = np.random.normal(loc=media_preco_m2, scale=std_preco_m2, size=n_linhas)
        preco_m2_vetor = np.clip(preco_m2_vetor, a_min=800.0, a_max=None)
        df['Valor'] = (df['Metragem'] * preco_m2_vetor).round(2)
    else:
        df['Valor'] = np.random.normal(loc=media_valor_indep, scale=std_valor_indep, size=n_linhas)
        df['Valor'] = np.clip(df['Valor'], a_min=20000.0, a_max=None).round(2)
        
    df.sort_values(by=['CPF', 'Valor'], ascending=[True, False], inplace=True)
    df['Imovel_Excedente'] = df.groupby('CPF').cumcount() > 0
    df['Locacao'] = df['Imovel_Excedente'] & (np.random.rand(n_linhas) < taxa_ocupacao_mercado)
    df['Aluguel'] = np.where(df['Imovel_Excedente'], "Sim", "Não")
    df['Locado'] = np.where(df['Locacao'], "Sim", "Não")
    
    # Variância de aluguel: fator aleatório
    variancia_aluguel = np.random.normal(loc=1.0, scale=variancia_aluguel_std, size=n_linhas)
    # Todos os imóveis excedentes (Aluguel = "Sim") recebem um Valor de Aluguel, mesmo se Locado = Não
    df['Valor_Aluguel'] = np.where(
        df['Imovel_Excedente'], 
        np.maximum(0.0, (df['Valor'] * taxa_aluguel_mensal * variancia_aluguel).round(2)), 
        0.0
    )
    
    df.drop(['CPF_ID', 'Imovel_Excedente', 'Locacao'], axis=1, inplace=True)
    df = df.sample(frac=1).reset_index(drop=True)
    
    return df

@st.cache_data(show_spinner="Calculando Imposto Progressivo e Função Social...")
def calcular_imposto_imobiliario(
    df,
    t_base=0.005,             
    y_ref=0.005,              
    alpha=2.0,                
    base_pg=1.5,              
    limite_desconto=0.8,      
    peso_progressividade=1.0  
):
    df_calc = df.copy()
    
    v_mediana = df_calc['Valor'].median()
    
    # ETAPA 1: Pilar C - Fator de Função Social (Redutor)
    # O cálculo do desconto só ocorre se o imóvel estiver locado de fato
    df_calc['Y_real'] = np.where(
        (df_calc['Valor'] > 0) & (df_calc['Locado'] == "Sim"), 
        df_calc['Valor_Aluguel'] / df_calc['Valor'], 
        0.0
    )
    condicao_desconto = (df_calc['Y_real'] > 0) & (df_calc['Y_real'] < y_ref)
    
    df_calc['Desconto_D'] = np.where(
        condicao_desconto,
        ((y_ref - df_calc['Y_real']) / y_ref) * alpha,
        0.0
    )
    
    df_calc['Desconto_D'] = np.clip(df_calc['Desconto_D'], a_min=0.0, a_max=limite_desconto)
    df_calc['V_trib'] = df_calc['Valor'] * (1 - df_calc['Desconto_D'])
    
    # ETAPA 2: Pilar A - Alíquota Proporcional Relativa (NOVO CONTROLE)
    razao_valor = np.where(df_calc['V_trib'] > 0, df_calc['V_trib'] / v_mediana, 0.0)
    df_calc['Taxa_imovel'] = t_base * (razao_valor ** peso_progressividade)
    
    # ETAPA 3: Pilar B - Multiplicador de Acúmulo por CPF
    contagem = df_calc.groupby('CPF').size().reset_index(name='N_Propriedades')
    df_calc = df_calc.merge(contagem, on='CPF', how='left')
    
    df_calc['Multiplicador_M'] = np.maximum(1.0, base_pg ** (df_calc['N_Propriedades'] - 1))
    
    # ETAPA 4: Alíquota Efetiva e Imposto Final
    df_calc['Imposto_Atual'] = (df_calc['Valor'] * t_base).round(2)
    df_calc['Imposto_Devido'] = (df_calc['Valor'] * df_calc['Taxa_imovel'] * df_calc['Multiplicador_M']).round(2)
    df_calc['Diferenca'] = (df_calc['Imposto_Devido'] - df_calc['Imposto_Atual']).round(2)
    df_calc['Diferenca_Pct'] = np.where(df_calc['Imposto_Atual'] > 0, df_calc['Diferenca'] / df_calc['Imposto_Atual'], 0.0)
    df_calc['Aliquota_Efetiva'] = np.where(df_calc['Valor'] > 0, df_calc['Imposto_Devido'] / df_calc['Valor'], 0.0)
    
    return df_calc


# =========================================================================
# FUNÇÕES DE FORMATAÇÃO (ESTILO BRASILEIRO)
# =========================================================================
def formata_moeda(valor):
    if pd.isna(valor) or valor == np.inf: return "N/A"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formata_percentual(valor):
    if pd.isna(valor) or valor == np.inf: return "N/A"
    return f"{(valor * 100):,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_mega_fortunas(valor):
    if pd.isna(valor) or valor == np.inf: return "Infinito / Erro"
    if valor < 10_000_000: return formata_moeda(valor)
    
    escalas = [
        (10**36, 'Undecilhões'),
        (10**33, 'Decilhões'),
        (10**30, 'Nonilhões'),
        (10**27, 'Octilhões'),
        (10**24, 'Septilhões'),
        (10**21, 'Sextilhões'),
        (10**18, 'Quintilhões'),
        (10**15, 'Quatrilhões'), 
        (10**12, 'Trilhões'), 
        (10**9, 'Bilhões'), 
        (10**6, 'Milhões')
    ]
    
    for limite, sufixo in escalas:
        if valor >= limite:
            fatia = float(valor) / limite
            if fatia >= 1000:
                fatia_str = f"{fatia:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                fatia_str = f"{fatia:.2f}".replace('.', ',')
            return f"R$ {fatia_str} {sufixo}"
    return str(valor)

# =========================================================================
# INTERFACE DO STREAMLIT
# =========================================================================
st.title("🪙 Terminal de Tributação Imobiliária Multidimensional")
st.markdown("Bem-vindo ao sistema analítico de tributação inteligente. Este simulador calcula impostos progressivos com base na função social e acúmulo patrimonial.")

# Parâmetros na Barra Lateral
st.sidebar.header("Parâmetros do Simulador")

st.sidebar.subheader("Geração da Base Sintética")
n_linhas = st.sidebar.slider("Número de Imóveis (Tamanho da Base)", min_value=50000, max_value=3000000, value=100000, step=50000)
concentracao_fundiaria = st.sidebar.slider("Concentração Fundiária (Desigualdade) (Sugestão: 1.5)", 0.5, 3.0, 1.5, 0.1)

usar_preco_m2 = st.sidebar.toggle("Calcular valor via preço/m²?", value=True)
media_metragem = st.sidebar.number_input("Média da Metragem (m²)", value=95.0, step=5.0)
std_metragem = st.sidebar.number_input("Desvio Padrão Metragem", value=100.0, step=10.0)

if usar_preco_m2:
    media_preco_m2 = st.sidebar.number_input("Preço Médio do m² (R$)", value=8000.0, step=500.0)
    std_preco_m2 = st.sidebar.number_input("Desvio Padrão Preço m² (R$)", value=7000.0, step=500.0)
    media_valor_indep = 500000.0
    std_valor_indep = 150000.0
else:
    media_valor_indep = st.sidebar.number_input("Valor Médio do Imóvel (R$)", value=500000.0, step=10000.0)
    std_valor_indep = st.sidebar.number_input("Desvio Padrão Valor do Imóvel (R$)", value=150000.0, step=10000.0)
    media_preco_m2 = 8000.0
    std_preco_m2 = 7000.0

taxa_ocupacao_mercado = st.sidebar.slider("Taxa de Ocupação (% Imóveis Alugados)", 0.0, 1.0, 0.85, 0.05)
taxa_aluguel_mensal = st.sidebar.number_input("Taxa Mensal Aluguel (%)", value=0.5, step=0.1) / 100.0
variancia_aluguel_std = st.sidebar.number_input("Variância Aluguel (Desvio Padrão %)", value=15.0, step=1.0) / 100.0

st.sidebar.subheader("Ligar/Desligar Pilares")
enable_progressividade = st.sidebar.toggle("Progressividade", value=True)
enable_acumulo = st.sidebar.toggle("Acúmulo de Propriedades", value=True)
enable_funcao_social = st.sidebar.toggle("Função Social (Desconto)", value=False)

st.sidebar.subheader("Cálculo do Imposto Algorítmico")
t_base = st.sidebar.number_input("Alíquota Base (T_base) % (Sugestão: 1.0%)", value=1.0, step=0.1) / 100.0
peso_progressividade = st.sidebar.slider("Progressividade Relação Preço (P) (Sugestão: 0.8)", 0.0, 3.0, 0.8, 0.1)
base_pg = st.sidebar.number_input("Fator PG para Acúmulo de Propriedades (Sugestão: 1.0071)", min_value=1.0000, max_value=2.0000, value=1.0071, step=0.0001, format="%.4f")
alpha = st.sidebar.number_input("Fator de Estímulo para o Redutor Social (α) (Sugestão: 0.20)", min_value=0.0, max_value=3.0, value=0.20, step=0.01, format="%.2f")
limite_desconto = st.sidebar.slider("Trava Máxima Desconto Social (Sugestão: 50%)", 0, 100, 50, 5) / 100.0

# Geração e Cálculo
df_base = gerar_base_imobiliaria(
    n_linhas=n_linhas, 
    concentracao_fundiaria=concentracao_fundiaria,
    media_metragem=media_metragem,
    std_metragem=std_metragem,
    usar_preco_m2=usar_preco_m2,
    media_preco_m2=media_preco_m2,
    std_preco_m2=std_preco_m2,
    media_valor_indep=media_valor_indep,
    std_valor_indep=std_valor_indep,
    taxa_ocupacao_mercado=taxa_ocupacao_mercado,
    taxa_aluguel_mensal=taxa_aluguel_mensal,
    variancia_aluguel_std=variancia_aluguel_std
)

# Cálculo do Y_ref baseado na mediana da base
df_locados = df_base[(df_base['Locado'] == 'Sim') & (df_base['Valor'] > 0)]
if not df_locados.empty:
    y_ref = (df_locados['Valor_Aluguel'] / df_locados['Valor']).median()
else:
    y_ref = 0.005

# Aplica os toggles para anular as variáveis se estiverem desligados
_alpha = alpha if enable_funcao_social else 0.0
_peso_progressividade = peso_progressividade if enable_progressividade else 0.0
_base_pg = base_pg if enable_acumulo else 1.0

df_impostos = calcular_imposto_imobiliario(
    df=df_base,
    t_base=t_base,
    y_ref=y_ref,
    alpha=_alpha,
    base_pg=_base_pg,
    limite_desconto=limite_desconto,
    peso_progressividade=_peso_progressividade
)

@st.dialog("Detalhamento de Imóveis do Contribuinte", width="large")
def popup_detalhes(cpf_id, pessoa_nome, nome_casta, patrimonio):
    st.markdown(f"<div style='text-align: center; color: #ffffff; font-size: 1.6em; font-weight: bold; margin-bottom: 0px;'>{pessoa_nome}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align: center; color: #ff6600; font-size: 1.1em; margin-bottom: 20px;'>{nome_casta}</div>", unsafe_allow_html=True)
    st.markdown(f"**CPF:** `{cpf_id}` | **Patrimônio Total:** `{formata_moeda(patrimonio)}`")
    
    df_detalhes = df_impostos[df_impostos['CPF'] == cpf_id].copy()
    
    df_exibicao = pd.DataFrame()
    df_exibicao['Valor do Imóvel'] = df_detalhes['Valor'].apply(formata_moeda)
    df_exibicao['Alíquota Prog. (PA)'] = df_detalhes['Taxa_imovel'].apply(formata_percentual)
    df_exibicao['Fator Acúmulo (PG)'] = df_detalhes['Multiplicador_M'].apply(lambda x: f"{x:.4f}x")
    df_exibicao['Alíquota Efetiva'] = df_detalhes['Aliquota_Efetiva'].apply(formata_percentual)
    df_exibicao['Imposto Atual'] = df_detalhes['Imposto_Atual'].apply(formata_moeda)
    df_exibicao['Imposto Novo'] = df_detalhes['Imposto_Devido'].apply(formata_moeda)
    df_exibicao['Diferença (R$)'] = df_detalhes['Diferenca'].apply(formata_moeda)
    df_exibicao['Diferença (%)'] = df_detalhes['Diferenca_Pct'].apply(lambda x: f"{x*100:+.2f}%".replace(".", ","))
    
    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

def renderizar_card_cpf(cpf_id, pessoa_nome, nome_casta, patrimonio, imposto_novo, imposto_atual, diferenca, qtd_imoveis, aliquota_media, key_suffix=""):
    cor_dif = "#4ADE80" if diferenca >= 0 else "#EF553B"
    sinal_dif = "+" if diferenca >= 0 else ""
    
    with st.container(border=True):
        st.markdown(f"<div style='text-align: center; color: #ffffff; font-size: 1.6em; font-weight: bold; margin-bottom: 5px;'>{pessoa_nome}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center; color: #ff6600; font-size: 1.1em; margin-bottom: 5px;'>{nome_casta}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='text-align: center; font-size: 0.9em; margin-bottom: 15px; color: #00ffff;'>Patrimônio: <b>{formata_moeda(patrimonio)}</b></div>", unsafe_allow_html=True)
        
        html_card = f"""
        <div style="display: flex; justify-content: center; margin-bottom: 15px;">
            <div style="display: flex; flex-direction: column; width: 95%; font-size: 0.95em; color: #E0E0E0;">
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #444;">
                    <span style="color: #D4AF37;"><b>Métrica</b></span>
                    <span style="color: #D4AF37;"><b>Valor</b></span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                    <span>Imposto Atual Base</span>
                    <span style="color: #6B8E23; font-weight: bold;">{formata_moeda(imposto_atual)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                    <span>Imposto Progressivo</span>
                    <span style="color: #6B8E23; font-weight: bold;">{formata_moeda(imposto_novo)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                    <span>Diferença</span>
                    <span style="color: {cor_dif}; font-weight: bold;">{sinal_dif}{formata_moeda(diferenca)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                    <span>Alíquota Média</span>
                    <span style="color: #6B8E23; font-weight: bold;">{formata_percentual(aliquota_media)}</span>
                </div>
                <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                    <span>Quantidade de Imóveis</span>
                    <span style="color: #6B8E23; font-weight: bold;">{int(qtd_imoveis)}</span>
                </div>
            </div>
        </div>
        """
        st.markdown(html_card, unsafe_allow_html=True)
        
        if st.button("Detalhamento", key=f"btn_{cpf_id}_{key_suffix}", use_container_width=True):
            popup_detalhes(cpf_id, pessoa_nome, nome_casta, patrimonio)

# Separação por Abas
tab0, tab_mercado, tab1, tab2, tab_castas, tab_macro = st.tabs([
    "Onepage (Didático)", 
    "Análises do Mercado Imobiliário", 
    "Panorama da Arrecadação", 
    "Lista de CPF", 
    "Personas",
    "Analise Macro econômica"
])

with tab0:
    st.header("Simulador Didático: Entendendo a Fórmula")
    st.markdown("Veja como cada pilar que você liga/desliga na barra lateral afeta a equação final de imposto para um imóvel.")
    
    formulas_container = st.container()
    
    if enable_funcao_social and not enable_progressividade:
        st.warning("⚠️ **Atenção:** Como a Progressividade está **desligada** ($P=0$), o Desconto de Função Social ($D_{social}$) perde o efeito, pois ele atua reduzindo o impacto progressivo sobre o valor do imóvel.")
    
    st.markdown("---")
    
    mediana_mercado = df_base['Valor'].median() if not df_base.empty else 500000.0
    
    st.subheader("Métricas de Referência da Base")
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric("Valor Mediano dos Imóveis (M)", formata_moeda(mediana_mercado))
    with m_col2:
        st.metric("Yield Mediano Praticado (Y_ref)", formata_percentual(y_ref))
    
    st.markdown("---")
    st.subheader("Teste com um Imóvel Fictício")
    
    colA, colB, colC = st.columns(3)
    sim_valor = colA.number_input("Valor do Imóvel (V)", value=500000.0, step=50000.0)
    sim_aluguel = colB.number_input("Valor do Aluguel Mensal", value=2500.0, step=100.0)
    sim_n_imoveis = colC.number_input("Qtd. de Imóveis do Proprietário (N)", min_value=1, value=1)
    
    # Cálculo manual para o imóvel fictício espelhando a função base
    sim_y_real = sim_aluguel / sim_valor if sim_valor > 0 else 0
    sim_desconto = 0.0
    if enable_funcao_social and sim_y_real > 0 and sim_y_real < y_ref:
        sim_desconto = ((y_ref - sim_y_real) / y_ref) * alpha
        sim_desconto = min(sim_desconto, limite_desconto)
        
    sim_v_trib = sim_valor * (1 - sim_desconto)
    sim_razao = sim_v_trib / mediana_mercado if mediana_mercado > 0 else 1
    sim_taxa = t_base * (sim_razao ** _peso_progressividade)
    sim_mult = max(1.0, _base_pg ** (sim_n_imoveis - 1))
    
    sim_imposto = sim_valor * sim_taxa * sim_mult
    sim_aliquota_efetiva = sim_imposto / sim_valor if sim_valor > 0 else 0
    
    # Montagem da Fórmula LaTeX Dinâmica (Teórica)
    latex_formula = r"Imposto = V \times T_{base}"
    if enable_progressividade:
        if enable_funcao_social:
            latex_formula += r" \times \left[ \frac{V \times \left(1 - D_{social}\right)}{M} \right]^P"
        else:
            latex_formula += r" \times \left( \frac{V}{M} \right)^P"
    if enable_acumulo:
        latex_formula += r" \times G^{(N - 1)}"
        
    # Montagem da Fórmula LaTeX Dinâmica (Preenchida)
    v_str = f"{sim_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    t_base_str = f"{t_base:.4f}".replace(".", ",")
    d_social_str = f"{sim_desconto:.4f}".replace(".", ",")
    m_str = f"{mediana_mercado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    p_str = f"{_peso_progressividade:.2f}".replace(".", ",")
    g_str = f"{_base_pg:.2f}".replace(".", ",")
    imposto_str = f"{sim_imposto:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    latex_filled = rf"{imposto_str} = {v_str} \times {t_base_str}"
    if enable_progressividade:
        if enable_funcao_social:
            latex_filled += rf" \times \left[ \frac{{{v_str} \times (1 - {d_social_str})}}{{{m_str}}} \right]^{{{p_str}}}"
        else:
            latex_filled += rf" \times \left( \frac{{{v_str}}}{{{m_str}}} \right)^{{{p_str}}}"
    if enable_acumulo:
        latex_filled += rf" \times {g_str}^{{({sim_n_imoveis} - 1)}}"
        
    with formulas_container:
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            with st.container(border=True):
                st.markdown("<div style='text-align: center; font-weight: bold; margin-bottom: 10px;'>Fórmula Base:</div>", unsafe_allow_html=True)
                st.latex(latex_formula)
        with f_col2:
            with st.container(border=True):
                st.markdown("<div style='text-align: center; font-weight: bold; margin-bottom: 10px;'>Fórmula Preenchida:</div>", unsafe_allow_html=True)
                st.latex(latex_filled)
        
        if enable_funcao_social:
            latex_dsocial_base = r"D_{social} = \alpha \times \frac{Y_{ref} - Y_{real}}{Y_{ref}}"
            
            alpha_str = f"{alpha:.2f}".replace(".", ",")
            y_ref_str = f"{y_ref:.4f}".replace(".", ",")
            y_real_str = f"{sim_y_real:.4f}".replace(".", ",")
            
            if sim_y_real > 0 and sim_y_real < y_ref:
                latex_dsocial_filled = rf"{d_social_str} = {alpha_str} \times \frac{{{y_ref_str} - {y_real_str}}}{{{y_ref_str}}}"
            else:
                latex_dsocial_filled = rf"{d_social_str} = 0 \text{{ (Fora dos critérios)}}"
            
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                with st.container(border=True):
                    st.markdown("<div style='text-align: center; font-weight: bold; margin-bottom: 10px;'>Fórmula Função Social ($D_{social}$) Base:</div>", unsafe_allow_html=True)
                    st.latex(latex_dsocial_base)
            with d_col2:
                with st.container(border=True):
                    st.markdown("<div style='text-align: center; font-weight: bold; margin-bottom: 10px;'>Fórmula Função Social ($D_{social}$) Preenchida:</div>", unsafe_allow_html=True)
                    st.latex(latex_dsocial_filled)
            
    res1, res2, res3, res4 = st.columns(4)
    with res1:
        with st.container(border=True):
            st.metric("Imposto a Pagar (Anual)", formata_moeda(sim_imposto))
    with res2:
        with st.container(border=True):
            st.metric("Alíquota Efetiva Aplicada", formata_percentual(sim_aliquota_efetiva))
    with res3:
        with st.container(border=True):
            st.metric("Desconto de Função Social", formata_percentual(sim_desconto))
    with res4:
        with st.container(border=True):
            st.metric(r"Yield Real Praticado ($Y_{real}$)", formata_percentual(sim_y_real))
            
    st.markdown("<br>", unsafe_allow_html=True)
    res5, res6, res7 = st.columns(3)
    with res5:
        with st.container(border=True):
            st.metric(r"Alíquota Base ($T_{base}$)", formata_percentual(t_base))
    with res6:
        with st.container(border=True):
            st.metric("Alíquota Relação Preço", formata_percentual(sim_taxa))
    with res7:
        with st.container(border=True):
            st.metric("Alíquota Acúmulo de propriedades", f"{sim_mult:.4f}x".replace(".", ","))


with tab_mercado:
    st.header("Análises do Mercado Imobiliário")
    st.markdown("Esta aba mostra os dados da base gerada **antes** de qualquer cálculo de impostos. É uma visão pura da cidade simulada.")
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Valor Total do Mercado", formatar_mega_fortunas(df_base['Valor'].sum()))
    col_m2.metric("Valor Mediano do Imóvel", formata_moeda(df_base['Valor'].median()))
    col_m3.metric("Metragem Média", f"{df_base['Metragem'].mean():.2f} m²")
    pct_alugados = ((df_base['Locado'] == 'Sim').sum() / len(df_base)) * 100
    col_m4.metric("Imóveis Alugados", f"{pct_alugados:.1f}%")
    
    st.markdown("---")
    
    # Amostra para gráficos mais rápidos
    df_plot_mercado = df_base.sample(min(20000, len(df_base))).copy()
    
    c1, c2 = st.columns(2)
    
    with c1:
        fig_hist_val = px.histogram(
            df_plot_mercado, 
            x="Valor", 
            nbins=50, 
            title="Distribuição de Valores dos Imóveis",
            template="plotly_dark",
            color_discrete_sequence=["#00CC96"]
        )
        fig_hist_val.update_layout(xaxis_title="Valor (R$)", yaxis_title="Frequência")
        
        mean_val = df_plot_mercado['Valor'].mean()
        median_val = df_plot_mercado['Valor'].median()
        fig_hist_val.add_vline(x=mean_val, line_dash="dash", line_color="white", annotation_text="Média", annotation_position="top right")
        fig_hist_val.add_vline(x=median_val, line_dash="dot", line_color="yellow", annotation_text="Mediana", annotation_position="top left")
        
        st.plotly_chart(fig_hist_val, use_container_width=True)
        
    with c2:
        fig_hist_met = px.histogram(
            df_plot_mercado, 
            x="Metragem", 
            nbins=50, 
            title="Distribuição de Metragens",
            template="plotly_dark",
            color_discrete_sequence=["#AB63FA"]
        )
        fig_hist_met.update_layout(xaxis_title="Metragem (m²)", yaxis_title="Frequência")
        
        mean_met = df_plot_mercado['Metragem'].mean()
        median_met = df_plot_mercado['Metragem'].median()
        fig_hist_met.add_vline(x=mean_met, line_dash="dash", line_color="white", annotation_text="Média", annotation_position="top right")
        fig_hist_met.add_vline(x=median_met, line_dash="dot", line_color="yellow", annotation_text="Mediana", annotation_position="top left")
        
        st.plotly_chart(fig_hist_met, use_container_width=True)
        
    c3, c4 = st.columns(2)
    
    with c3:
        # Pie chart Locacao
        pie_data = df_plot_mercado['Locado'].value_counts().reset_index()
        pie_data.columns = ['Status', 'Contagem']
        pie_data['Status'] = pie_data['Status'].map({'Sim': 'Alugados', 'Não': 'Uso Próprio / Vazios'})
        
        fig_pie = px.pie(
            pie_data, 
            names='Status', 
            values='Contagem', 
            title="Proporção de Imóveis Alugados",
            template="plotly_dark",
            hole=0.4,
            color='Status',
            color_discrete_map={'Alugados': '#EF553B', 'Uso Próprio / Vazios': '#636EFA'}
        )
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c4:
        # Scatter area vs valor
        fig_scatter = px.scatter(
            df_plot_mercado, 
            x="Metragem", 
            y="Valor", 
            opacity=0.3,
            title="Relação: Metragem vs Valor",
            template="plotly_dark",
            color_discrete_sequence=["#FFA15A"]
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
        
    st.markdown("---")
    st.subheader("Análises de Aluguel e Yield")
    
    df_aluguel = df_plot_mercado[df_plot_mercado['Aluguel'] == 'Sim'].copy()
    if not df_aluguel.empty:
        df_aluguel['Yield_Mensal_Pct'] = (df_aluguel['Valor_Aluguel'] / df_aluguel['Valor']) * 100
        
        col_a1, col_a2, col_a3, col_a4 = st.columns(4)
        col_a1.metric("Valor Médio do Aluguel", formata_moeda(df_aluguel['Valor_Aluguel'].mean()))
        col_a2.metric("Valor Mediano do Aluguel", formata_moeda(df_aluguel['Valor_Aluguel'].median()))
        col_a3.metric("Yield Mensal Médio", f"{df_aluguel['Yield_Mensal_Pct'].mean():.2f}%".replace(".", ","))
        col_a4.metric("Yield Mensal Mediano", f"{df_aluguel['Yield_Mensal_Pct'].median():.2f}%".replace(".", ","))
        
        ca1, ca2 = st.columns(2)
        with ca1:
            fig_hist_aluguel = px.histogram(
                df_aluguel, 
                x="Valor_Aluguel", 
                nbins=50, 
                title="Distribuição do Valor do Aluguel",
                template="plotly_dark",
                color_discrete_sequence=["#F2E51A"]
            )
            fig_hist_aluguel.update_layout(
                xaxis_title="Aluguel Mensal (R$)", 
                yaxis_title="Frequência"
            )
            st.plotly_chart(fig_hist_aluguel, use_container_width=True)
            
        with ca2:
            fig_hist_yield = px.histogram(
                df_aluguel, 
                x="Yield_Mensal_Pct", 
                nbins=50, 
                title="Distribuição do Yield Mensal (%)",
                template="plotly_dark",
                color_discrete_sequence=["#FF6692"]
            )
            fig_hist_yield.update_layout(
                xaxis_title="Yield Mensal (%)", 
                yaxis_title="Frequência"
            )
            st.plotly_chart(fig_hist_yield, use_container_width=True)
    else:
        st.info("Nenhum imóvel disponível para aluguel nesta simulação.")

with tab1:
    st.header("Panorama da Arrecadação e Tributação")
    
    # Cálculos Globais
    total_imposto = df_impostos['Imposto_Devido'].sum()
    total_patrimonio = df_impostos['Valor'].sum()
    aliquota_media_global = total_imposto / total_patrimonio if total_patrimonio > 0 else 0
    cpfs_unicos = df_impostos['CPF'].nunique()
    ticket_medio = total_imposto / cpfs_unicos if cpfs_unicos > 0 else 0
    
    imposto_atual = df_impostos['Imposto_Atual'].sum()
    diferenca = df_impostos['Diferenca'].sum()
    diferenca_pct = (diferenca / imposto_atual) if imposto_atual > 0 else 0
    diferenca_pct_str = f"{diferenca_pct * 100:.2f}%".replace(".", ",")
    
    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Imposto Total (Novo Algoritmo)", formatar_mega_fortunas(total_imposto))
    col_t2.metric(f"Imposto Atual (Apenas T_base)", formatar_mega_fortunas(imposto_atual))
    col_t3.metric("Diferença de Arrecadação", formatar_mega_fortunas(diferenca), delta=diferenca_pct_str)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_b1, col_b2, col_b3, col_b4 = st.columns(4)
    col_b1.metric("Valor Patrimonial Base", formatar_mega_fortunas(total_patrimonio))
    col_b2.metric("Alíquota Efetiva Global (Algoritmo)", formata_percentual(aliquota_media_global))
    col_b3.metric("Ticket Médio por CPF", formata_moeda(ticket_medio))
    col_b4.metric("Total de Contribuintes (CPFs)", f"{cpfs_unicos:,.0f}".replace(',', '.'))
    
    st.markdown("---")
    st.subheader("Impacto por Faixas de Patrimônio (Centrado na Mediana)")
    st.markdown("Comparativo do impacto financeiro dividindo a população em 10 faixas. O **Grupo 4** isola a classe média (Mediana do Imóvel ± R$ 80 mil), dividindo os extremos em subgrupos.")
    
    df_cpfs_tab1 = df_impostos.groupby('CPF').agg(
        Qtd_Imoveis=('Valor', 'count'),
        Valor_Patrimonio_Total=('Valor', 'sum'),
        Imposto_Atual_Total=('Imposto_Atual', 'sum'),
        Imposto_Total_Devido=('Imposto_Devido', 'sum'),
        Diferenca_Total=('Diferenca', 'sum')
    ).reset_index()
    
    mediana_imovel = df_impostos['Valor'].median()
    m_low = max(0, mediana_imovel - 80000)
    m_high = mediana_imovel + 80000
    
    mask_lower = df_cpfs_tab1['Valor_Patrimonio_Total'] < m_low
    mask_upper = df_cpfs_tab1['Valor_Patrimonio_Total'] > m_high
    
    lower_vals = df_cpfs_tab1.loc[mask_lower, 'Valor_Patrimonio_Total']
    upper_vals = df_cpfs_tab1.loc[mask_upper, 'Valor_Patrimonio_Total']
    
    def get_bin_edges(series, q):
        if len(series) < q:
            return None
        try:
            edges = list(pd.qcut(series, q=q, retbins=True, duplicates='drop')[1])
            if len(edges) - 1 < q:
                return None
            return edges
        except:
            return None

    lower_edges = get_bin_edges(lower_vals, 3)
    if not lower_edges:
        lower_edges = [0, m_low/3, 2*m_low/3, m_low]
    else:
        lower_edges[0] = 0
        lower_edges[-1] = m_low
        
    upper_edges = get_bin_edges(upper_vals, 6)
    if not upper_edges:
        upper_edges = [m_high, m_high*1.5, m_high*2, m_high*3, m_high*4, m_high*5, float('inf')]
    else:
        upper_edges[0] = m_high
        upper_edges[-1] = float('inf')
        
    bins = sorted(list(set(lower_edges[:-1] + [m_low, m_high] + upper_edges[1:])))
    
    if len(bins) < 11:
        df_cpfs_tab1['Faixa_Idx'] = pd.qcut(df_cpfs_tab1['Valor_Patrimonio_Total'], q=10, labels=False, duplicates='drop')
    else:
        df_cpfs_tab1['Faixa_Idx'] = pd.cut(df_cpfs_tab1['Valor_Patrimonio_Total'], bins=bins, labels=False, include_lowest=True)
        
    faixas_grp = df_cpfs_tab1.groupby('Faixa_Idx').agg(
        Valor_Min=('Valor_Patrimonio_Total', 'min'),
        Valor_Max=('Valor_Patrimonio_Total', 'max'),
        Valor_Patrimonio_Total=('Valor_Patrimonio_Total', 'sum'),
        Imposto_Atual_Total=('Imposto_Atual_Total', 'sum'),
        Imposto_Total_Devido=('Imposto_Total_Devido', 'sum'),
        Diferenca_Total=('Diferenca_Total', 'sum'),
        Qtd_Imoveis=('Qtd_Imoveis', 'sum'),
        Qtd_CPF=('CPF', 'count')
    ).reset_index()
    
    num_grupos = len(faixas_grp)
    for row_idx in range(0, num_grupos, 5):
        cols = st.columns(5)
        for col_idx in range(5):
            curr_idx = row_idx + col_idx
            if curr_idx < num_grupos:
                row_data = faixas_grp.iloc[curr_idx]
                f_idx = curr_idx
                q_min = row_data['Valor_Min']
                q_max = row_data['Valor_Max']
                
                titulo_grupo = f"Grupo {f_idx+1}"
                if len(bins) == 11 and f_idx == 3:
                    titulo_grupo = f"Grupo 4 (Mediana)"
                    
                nome_faixa = f"{titulo_grupo}<br><span style='font-size: 0.70em; color: #aaaaaa;'>{formatar_mega_fortunas(q_min)} a {formatar_mega_fortunas(q_max)}</span>"
                if q_min == q_max:
                    nome_faixa = f"{titulo_grupo}<br><span style='font-size: 0.70em; color: #aaaaaa;'>{formatar_mega_fortunas(q_min)}</span>"
                
                q_patrimonio = row_data['Valor_Patrimonio_Total']
                q_imposto_novo = row_data['Imposto_Total_Devido']
                q_imposto_hoje = row_data['Imposto_Atual_Total']
                q_diferenca = row_data['Diferenca_Total']
                q_qtd_cpfs = row_data['Qtd_CPF']
                
                cor_dif = "#4ADE80" if q_diferenca >= 0 else "#EF553B"
                sinal_dif = "+" if q_diferenca >= 0 else ""
                
                html_card = f"""
                <div style="display: flex; justify-content: center; margin-bottom: 10px;">
                    <div style="display: flex; flex-direction: column; width: 100%; font-size: 0.82em; color: #E0E0E0;">
                        <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #444;">
                            <span style="color: #D4AF37;"><b>Métrica</b></span>
                            <span style="color: #D4AF37;"><b>Valor</b></span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                            <span>Contribuintes</span>
                            <span style="color: #6B8E23; font-weight: bold;">{q_qtd_cpfs:,.0f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                            <span>Imp. Atual ({t_base*100:.1f}%)</span>
                            <span style="color: #6B8E23; font-weight: bold;">{formatar_mega_fortunas(q_imposto_hoje)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                            <span>Imp. Progressivo</span>
                            <span style="color: #6B8E23; font-weight: bold;">{formatar_mega_fortunas(q_imposto_novo)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                            <span>Diferença</span>
                            <span style="color: {cor_dif}; font-weight: bold;">{sinal_dif}{formatar_mega_fortunas(q_diferenca)}</span>
                        </div>
                    </div>
                </div>
                """
                
                with cols[col_idx]:
                    with st.container(border=True):
                        st.markdown(f"<div style='text-align: center; color: #ffffff; font-size: 1.05em; font-weight: bold; margin-bottom: 5px;'>{nome_faixa}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align: center; font-size: 0.85em; margin-bottom: 10px; color: #00ffff;'>Patrimônio: <b>{formatar_mega_fortunas(q_patrimonio)}</b></div>", unsafe_allow_html=True)
                        st.markdown(html_card, unsafe_allow_html=True)
                
    st.markdown("---")
    
    c_graf1, c_graf2 = st.columns(2)
    
    with c_graf1:
        st.subheader("Distribuição das Alíquotas Efetivas")
        # Histograma para ver onde a maioria cai
        # Filtrar valores extremos se necessário para o gráfico ficar bonito
        df_hist = df_impostos.copy()
        df_hist['Aliquota_Teto'] = df_hist['Aliquota_Efetiva'].clip(upper=0.1) # Teto visual de 10% para o histograma
        
        fig_hist_aliq = px.histogram(
            df_hist, 
            x="Aliquota_Teto", 
            nbins=50,
            title="Quantos imóveis pagam cada faixa de alíquota?",
            template="plotly_dark",
            color_discrete_sequence=["#00ff00"]
        )
        fig_hist_aliq.update_layout(
            xaxis_title="Alíquota Efetiva", 
            yaxis_title="Qtd. de Imóveis",
            xaxis=dict(tickformat='.1%')
        )
        st.plotly_chart(fig_hist_aliq, use_container_width=True)
        
    with c_graf2:
        st.subheader("Origem da Arrecadação (Uso Social)")
        # Quanto de dinheiro vem de imoveis alugados vs vazios
        origem_taxa = df_impostos.groupby('Locado')['Imposto_Devido'].sum().reset_index()
        origem_taxa['Locado'] = origem_taxa['Locado'].map({'Sim': 'Alugados', 'Não': 'Uso Próprio / Vazios'})
        
        fig_pie_tax = px.pie(
            origem_taxa, 
            names='Locado', 
            values='Imposto_Devido', 
            title="Proporção da Arrecadação em R$",
            template="plotly_dark",
            hole=0.4,
            color='Locado',
            color_discrete_map={'Alugados': '#EF553B', 'Uso Próprio / Vazios': '#636EFA'}
        )
        st.plotly_chart(fig_pie_tax, use_container_width=True)
    
    st.markdown("---")
    st.subheader("Impacto Multidimensional: Alíquota vs Valor do Imóvel")
    
    # Amostra para não travar o gráfico no browser
    df_plot = df_impostos.sample(min(10000, len(df_impostos))).copy()
    
    # 1. Limitamos o Eixo Y a 100% (1.0) para ver a curva da grande maioria da população
    df_plot['Aliquota_Visual'] = df_plot['Aliquota_Efetiva'].clip(upper=1.0)
    
    # 2. Limitamos a escala de cores a 50 propriedades. Senão, 1 mega-especulador ofusca todos.
    df_plot['N_Propriedades_Visual'] = df_plot['N_Propriedades'].clip(upper=50)
    
    # 3. Tamanho mínimo para os pontos (para não sumirem se o Desconto for 0)
    df_plot['Tamanho_Visual'] = df_plot['Desconto_D'] * 15 + 3
    
    fig = px.scatter(
        df_plot, 
        x="Valor", 
        y="Aliquota_Visual", 
        color="N_Propriedades_Visual", 
        size="Tamanho_Visual",
        size_max= 10,
        template="plotly_dark",
        title="Dispersão: Quanto maior o valor e acúmulo, maior a alíquota (Eixo X em Log)",
        color_continuous_scale="Turbo", # Paleta vibrante neon (Bloomberg style)
        opacity=0.7,
        hover_data={
            "N_Propriedades": True, 
            "Aliquota_Efetiva": True, 
            "Desconto_D": True, 
            "Tamanho_Visual": False, 
            "N_Propriedades_Visual": False,
            "Aliquota_Visual": False
        },
        labels={"Aliquota_Visual": "Alíquota Efetiva", "Valor": "Valor do Imóvel (R$)", "N_Propriedades_Visual": "Qtd. Imóveis (Acúmulo)"},
        log_x=True # Espalha os imóveis horizontalmente (desfaz o agrupamento no 0)
    )
    
    # Formatação especial (Cores de Fundo, Grades e Porcentagem no Eixo Y)
    fig.update_layout(
        plot_bgcolor='#050505', 
        paper_bgcolor='#050505', 
        font_color='#00ff00',
        xaxis=dict(gridcolor='#222222', title_font=dict(color='#ff6600')),
        yaxis=dict(gridcolor='#222222', tickformat='.1%', title_font=dict(color='#ff6600'))
    )
    st.plotly_chart(fig, use_container_width=True)


with tab2:
    st.header("Lista de CPF")
    st.markdown("Divisão das parcelas populacionais de contribuintes e impacto real.")
    
    ranking_cpf = df_impostos.groupby('CPF').agg(
        Qtd_Imoveis=('Valor', 'count'),
        Valor_Patrimonio_Total=('Valor', 'sum'),
        Multiplicador_Acumulo=('Multiplicador_M', 'max'),
        Desconto_Social_Medio=('Desconto_D', 'mean'),
        Imposto_Atual_Total=('Imposto_Atual', 'sum'),
        Imposto_Total_Devido=('Imposto_Devido', 'sum'),
        Diferenca_Total=('Diferenca', 'sum')
    ).reset_index()

    ranking_cpf['Aliquota_Média_Total'] = np.where(
        ranking_cpf['Valor_Patrimonio_Total'] > 0,
        (ranking_cpf['Imposto_Total_Devido'] / ranking_cpf['Valor_Patrimonio_Total']),
        0.0
    )

    st.markdown("### Dispersão: Número de Imóveis vs Riqueza Acumulada")
    st.markdown("💡 **Dica:** Clique em qualquer bolinha no gráfico para detalhar a situação daquele contribuinte!")
    
    col_grafico, col_detalhe = st.columns([2.5, 1])
    
    with col_grafico:
        fig_cpf = px.scatter(
            ranking_cpf, 
            x="Valor_Patrimonio_Total", 
            y="Qtd_Imoveis", 
            color="Aliquota_Média_Total",
            color_continuous_scale="turbo",
            opacity=1.0,
            hover_data={
                "CPF": True, 
                "Valor_Patrimonio_Total": True, 
                "Qtd_Imoveis": True,
                "Aliquota_Média_Total": True
            },
            labels={
                "Valor_Patrimonio_Total": "Riqueza Acumulada (R$)", 
                "Qtd_Imoveis": "Número de Imóveis", 
                "Aliquota_Média_Total": "Alíquota Média"
            },
            log_x=True
        )
        fig_cpf.update_traces(marker=dict(size=8, line=dict(width=0.5, color='DarkSlateGrey')))
        fig_cpf.update_layout(
            plot_bgcolor='#050505', 
            paper_bgcolor='#050505', 
            font_color='#00ff00',
            xaxis=dict(gridcolor='#222222', title_font=dict(color='#ff6600')),
            yaxis=dict(gridcolor='#222222', title_font=dict(color='#ff6600')),
            clickmode='event+select'
        )
        
        event_cpf = st.plotly_chart(fig_cpf, use_container_width=True, on_select="rerun")
        
    with col_detalhe:
        if event_cpf and "selection" in event_cpf and event_cpf["selection"].get("points"):
            ponto_selecionado = event_cpf["selection"]["points"][0]
            if "customdata" in ponto_selecionado and ponto_selecionado["customdata"]:
                cpf_selecionado = ponto_selecionado["customdata"][0]
                
                dados_cpf = ranking_cpf[ranking_cpf['CPF'] == cpf_selecionado].iloc[0]
                
                st.markdown(f"<div style='text-align: center; color: #ffffff; font-size: 1.2em; font-weight: bold; margin-bottom: 10px;'>Detalhes Selecionados</div>", unsafe_allow_html=True)
                
                renderizar_card_cpf(
                    cpf_id=cpf_selecionado, 
                    pessoa_nome="Contribuinte Selecionado", 
                    nome_casta=f"Encontrado via Gráfico", 
                    patrimonio=dados_cpf['Valor_Patrimonio_Total'], 
                    imposto_novo=dados_cpf['Imposto_Total_Devido'], 
                    imposto_atual=dados_cpf['Imposto_Atual_Total'],
                    diferenca=dados_cpf['Diferenca_Total'],
                    qtd_imoveis=dados_cpf['Qtd_Imoveis'], 
                    aliquota_media=dados_cpf['Aliquota_Média_Total'],
                    key_suffix="grafico"
                )
        else:
            st.markdown("<div style='text-align: center; color: #666666; margin-top: 150px;'><em>👈 Clique em um ponto no gráfico ao lado para exibir os detalhes aqui.</em></div>", unsafe_allow_html=True)




with tab_castas:
    st.header("Comparativo de 9 Castas Representativas")
    st.markdown("Foram selecionados 9 perfis reais da base (de diferentes faixas de patrimônio) para comparação detalhada.")
    
    ranking_cpf_castas = df_impostos.groupby('CPF').agg(
        Qtd_Imoveis=('Valor', 'count'),
        Valor_Patrimonio_Total=('Valor', 'sum'),
        Imposto_Atual_Total=('Imposto_Atual', 'sum'),
        Imposto_Total_Devido=('Imposto_Devido', 'sum'),
        Diferenca_Total=('Diferenca', 'sum')
    ).reset_index().sort_values(by='Valor_Patrimonio_Total', ascending=True)
    
    n_cpfs = len(ranking_cpf_castas)
    indices_castas = [
        0,                          # 1. Base (Menor patrimônio)
        int(n_cpfs * 0.10),         # 2. 10%
        int(n_cpfs * 0.25),         # 3. 25%
        int(n_cpfs * 0.50),         # 4. Mediana (50%)
        int(n_cpfs * 0.75),         # 5. 75%
        int(n_cpfs * 0.90),         # 6. 90%
        int(n_cpfs * 0.95),         # 7. 95%
        int(n_cpfs * 0.99),         # 8. 99%
        n_cpfs - 1                  # 9. Top 1 (Maior patrimônio)
    ]
    
    nomes_castas = [
        "Base da Pirâmide<br>(menor patrimônio)",
        "Percentil 10%",
        "Percentil 25%",
        "Classe Média<br>(mediana 50%)",
        "Classe Alta<br>(percentil 75%)",
        "Ricos<br>(percentil 90%)",
        "Super Ricos<br>(percentil 95%)",
        "Ultra Ricos<br>(percentil 99%)",
        "O Maior Latifundiário<br>(top 1)"
    ]
    
    pessoas_castas = [
        "Seu José",
        "Dona Maria",
        "Seu Raimundo",
        "Henrique",
        "Camila",
        "Lucas",
        "Augusto",
        "Gabriela",
        "Arthur"
    ]


    # Criando o grid 3x3
    for i in range(0, 9, 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < 9:
                idx = indices_castas[i+j]
                if idx >= n_cpfs:
                    idx = n_cpfs - 1
                cpf_selecionado = ranking_cpf_castas.iloc[idx]
                
                cpf_id = cpf_selecionado['CPF']
                nome_casta = nomes_castas[i+j]
                pessoa_nome = pessoas_castas[i+j]
                patrimonio = cpf_selecionado['Valor_Patrimonio_Total']
                qtd_imoveis = cpf_selecionado['Qtd_Imoveis']
                imposto_novo = cpf_selecionado['Imposto_Total_Devido']
                imposto_atual = cpf_selecionado['Imposto_Atual_Total']
                diferenca = cpf_selecionado['Diferenca_Total']
                
                aliquota_media = (imposto_novo / patrimonio) if patrimonio > 0 else 0
                
                with cols[j]:
                    renderizar_card_cpf(
                        cpf_id=cpf_id, 
                        pessoa_nome=pessoa_nome, 
                        nome_casta=nome_casta, 
                        patrimonio=patrimonio, 
                        imposto_novo=imposto_novo, 
                        imposto_atual=imposto_atual,
                        diferenca=diferenca,
                        qtd_imoveis=qtd_imoveis, 
                        aliquota_media=aliquota_media, 
                        key_suffix=f"{i}_{j}"
                    )

with tab_macro:
    st.header("Análise Macro Econômica")
    st.warning("Em construção, estamos sofrendo de falta de literatura sobre elasticidade dos alugueis urbanos", icon="🚧")



