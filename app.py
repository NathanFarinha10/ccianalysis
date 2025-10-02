# app_cci.py
import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import datetime
from dateutil.relativedelta import relativedelta
import google.generativeai as genai
from fpdf import FPDF
import os
from io import BytesIO
import json

# ==============================================================================
# INICIALIZAÇÃO E FUNÇÕES AUXILIARES
# ==============================================================================

def inicializar_session_state():
    """Garante que todos os valores de input e scores sejam inicializados no st.session_state apenas uma vez."""
    if 'state_initialized_cci' not in st.session_state:
        st.session_state.state_initialized_cci = True
        st.session_state.scores = {}
        st.session_state.map_data = None
        st.session_state.fluxo_cci_df = pd.DataFrame()

        # Ajuste no prazo padrão para ajustar o calendário de vencimento
        default_emissao = datetime.date(2024, 5, 1)
        default_prazo_meses = 120 # 10 anos
        default_vencimento = default_emissao + relativedelta(months=+default_prazo_meses)

        defaults = {
            # --- Chaves para a aba de Cadastro ---
            'op_nome': 'CCI Exemplo Residencial', 'op_codigo': 'CCIEX123',
            'op_emissor': 'Banco Exemplo S.A.', 'op_volume': 1500000.0,
            'op_taxa': 11.5, 'op_indexador': 'IPCA +', 'op_prazo': default_prazo_meses,
            'op_amortizacao': 'SAC', 'op_data_emissao': default_emissao,
            'op_data_vencimento': default_vencimento,

            # --- PILAR 1: Lastro Imobiliário (ROBUSTO) ---
            'credibilidade_avaliador': '1ª Linha Nacional', 'qualidade_comparaveis': 'Sim',
            'estresse_valor_perc': 15.0, 'fipezap_12m': 5.2, 'liquidez_dias': 120,
            'risco_oferta': 'Baixo, bairro consolidado', 'cidade_mapa': 'São Paulo, SP',
            'adequacao_produto': 'Ideal', 'reputacao_construtora': '1ª Linha',
            'estado_conservacao': 'Novo/Reformado', 'tipo_imovel': 'Residencial (Apartamento/Casa)',
            'analise_dominial_20a': True, 'cnds_verificadas': ['CND do Imóvel (IPTU)', 'CND do Devedor'],
            'dividas_propter_rem': True, 'risco_ambiental_imovel': 'Inexistente',

            # --- PILAR 2: Crédito e Devedor (ROBUSTO) ---
            'finalidade_credito': 'Financiamento de Aquisição',
            'historico_pagamento': 'Novo, sem histórico de pagamento',
            'valor_avaliacao_imovel': 2500000.0, 'saldo_devedor_credito': 1500000.0, 'ltv_operacao': 60.0,
            'tipo_lastro_credito': 'Crédito Único',
            'tipo_devedor': 'Pessoa Física',
            'parcela_mensal_pf': 12000.0, 'renda_mensal_pf': 45000.0,
            'outras_dividas_pf': 'Nenhuma Relevante', 'patrimonio_liquido_pf': '> R$ 1.000.000',
            'score_credito_devedor': 'Excelente (>800)',
            'dl_ebitda_pj': 2.5, 'liq_corrente_pj': 1.8, 'dscr_pj': 1.5,
            'num_devedores': 10, 'concentracao_top5': 60.0,
            'meses_decorridos_pgto': 12, 'maior_atraso_hist': 'Sem atrasos', 'inadimplencia_90d': 0.0,

            # --- PILAR 3: Estrutura da CCI (ROBUSTO) ---
            'reputacao_emissor': 'Banco de 1ª linha / Emissor especialista',
            'qualidade_servicer': 'Interna, com alta especialização',
            'fundo_reserva_pmts': 0.0, 'fundo_reserva_regra': False,
            'despesas_subordinadas': True, 'clareza_waterfall': 'Clara e bem definida',
            'qualidade_parecer_legal': 'Escritório de 1ª linha',
            'qualidade_relatorios': 'Alta, detalhados e frequentes',
            'garantias_adicionais': [],
            'seguros_mip_dfi': 'Sim, apólices vigentes e adequadas',
            'covenants_operacao': 'Fortes, com gatilhos objetivos',
            'saldo_inadimplente_90d': 0.0, 'parcelas_em_atraso_media': 0,
            'historico_renegociacao': 'Sem histórico de renegociação',

            # --- Precificação e Resultado ---
            'precificacao_duration_manual': 5.0, # Novo campo para duration manual
            'precificacao_ntnb': 6.15,
            'precificacao_cdi_proj': 10.25,
            'ajuste_final': 0,
            'justificativa_final': '',
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

@st.cache_data
def get_coords(city):
    if not city: return None
    try:
        geolocator = Nominatim(user_agent="cci_analyzer_app")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        location = geocode(city)
        if location: return pd.DataFrame({'lat': [location.latitude], 'lon': [location.longitude]})
    except Exception: return None

def create_gauge_chart(score, title):
    if score is None: score = 1.0
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=round(score, 2),
        title={'text': title, 'font': {'size': 20}},
        gauge={
            'axis': {'range': [1, 5], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "black", 'thickness': 0.3}, 'bgcolor': "white", 'borderwidth': 1, 'bordercolor': "gray",
            'steps': [
                {'range': [1, 2.5], 'color': '#dc3545'},
                {'range': [2.5, 3.75], 'color': '#ffc107'},
                {'range': [3.75, 5], 'color': '#28a745'}],
        }))
    fig.update_layout(height=250, margin={'t':40, 'b':40, 'l':30, 'r':30})
    return fig

def converter_score_para_rating(score):
    if score is None: return "N/A"
    if score >= 4.75: return 'brAAA(sf)'
    elif score >= 4.25: return 'brAA(sf)'
    elif score >= 3.75: return 'brA(sf)'
    elif score >= 3.25: return 'brBBB(sf)'
    elif score >= 2.75: return 'brBB(sf)'
    elif score >= 2.50: return 'brB(sf)'
    elif score >= 2.25: return 'brCCC(sf)'
    elif score >= 2.00: return 'brCC(sf)'
    elif score >= 1.50: return 'brC(sf)'
    else: return 'brD(sf)'

def ajustar_rating(rating_base, notches):
    escala = ['brD(sf)', 'brC(sf)','brCC(sf)','brCCC(sf)', 'brB(sf)', 'brBB(sf)', 'brBBB(sf)', 'brA(sf)', 'brAA(sf)', 'brAAA(sf)']
    try:
        idx_base = escala.index(rating_base)
        idx_final = max(0, min(len(escala) - 1, idx_base + notches))
        return escala[idx_final]
    except (ValueError, TypeError): return rating_base

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Relatório de Análise e Rating de CCI', 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def _write_text(self, text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.multi_cell(0, 10, self._write_text(title), 0, 'L')
        self.ln(4)

    def TabelaCadastro(self, ss):
        self.set_font('Arial', '', 10)
        line_height = self.font_size * 1.5
        col_width = self.epw / 4
        data = {
            "Nome da Operação:": ss.op_nome, "Código/Série:": ss.op_codigo,
            "Volume Emitido:": f"R$ {ss.op_volume:,.2f}", "Taxa:": f"{ss.op_indexador} {ss.op_taxa}% a.a.",
            "Data de Emissão:": ss.op_data_emissao.strftime('%d/%m/%Y'), "Vencimento:": ss.op_data_vencimento.strftime('%d/%m/%Y'),
            "Emissor:": ss.op_emissor, "Sistema Amortização:": ss.op_amortizacao,
        }
        for i, (label, value) in enumerate(data.items()):
            if i > 0 and i % 2 == 0: self.ln(line_height)
            self.set_font('Arial', 'B', 10)
            self.cell(col_width, line_height, self._write_text(label), border=1)
            self.set_font('Arial', '', 10)
            self.cell(col_width, line_height, self._write_text(str(value)), border=1)
        self.ln(line_height)
        self.ln(10)

    def TabelaScorecard(self, ss, pesos):
        self.set_font('Arial', 'B', 10)
        line_height = self.font_size * 1.5
        col_widths = [self.epw * 0.5, self.epw * 0.15, self.epw * 0.2, self.epw * 0.15]
        headers = ["Pilar de Análise", "Peso", "Pontuação (1-5)", "Score Ponderado"]
        for i, header in enumerate(headers): self.cell(col_widths[i], line_height, header, border=1, align='C')
        self.ln(line_height)
        self.set_font('Arial', '', 10)
        data = [
            ["Pilar 1: Lastro Imobiliário", f"{pesos['pilar1']*100:.0f}%", f"{ss.scores.get('pilar1', 0):.2f}", f"{ss.scores.get('pilar1', 0) * pesos['pilar1']:.2f}"],
            ["Pilar 2: Crédito e Devedor", f"{pesos['pilar2']*100:.0f}%", f"{ss.scores.get('pilar2', 0):.2f}", f"{ss.scores.get('pilar2', 0) * pesos['pilar2']:.2f}"],
            ["Pilar 3: Estrutura da CCI", f"{pesos['pilar3']*100:.0f}%", f"{ss.scores.get('pilar3', 0):.2f}", f"{ss.scores.get('pilar3', 0) * pesos['pilar3']:.2f}"],
        ]
        for row in data:
            for i, item in enumerate(row): self.cell(col_widths[i], line_height, item, border=1, align='C')
            self.ln(line_height)
        self.ln(10)

    def AnaliseIA(self, texto_analise):
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, self._write_text(texto_analise))
        self.ln(5)

def gerar_relatorio_pdf(ss):
    try:
        pdf = PDF()
        pdf.add_page()
        pdf.chapter_title('1. Dados Cadastrais da Operação')
        pdf.TabelaCadastro(ss)

        pesos_cci = {'pilar1': 0.45, 'pilar2': 0.40, 'pilar3': 0.15}
        pdf.chapter_title('2. Scorecard e Rating Final')
        pdf.TabelaScorecard(ss, pesos_cci)

        score_final_ponderado = sum(ss.scores.get(p, 1) * w for p, w in pesos_cci.items())
        rating_indicado = converter_score_para_rating(score_final_ponderado)
        rating_final = ajustar_rating(rating_indicado, ss.ajuste_final)

        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f"Score Final Ponderado: {score_final_ponderado:.2f}", 0, 1)
        pdf.cell(0, 10, f"Rating Final Atribuído: {rating_final}", 0, 1)
        pdf.set_font('Arial', 'B', 10)
        pdf.write(5, pdf._write_text(f"Justificativa do Comitê: {ss.justificativa_final}"))
        pdf.ln(10)

        pdf.chapter_title('3. Análise Qualitativa com IA Gemini')
        nomes_pilares = ["Lastro Imobiliário", "Crédito e Devedor", "Estrutura da CCI"]
        for i in range(1, 4): # Alterado para 4 para incluir até o pilar 3
            analise_key = f'analise_p{i}'
            if ss.get(analise_key):
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, f"Análise do Pilar {i}: {nomes_pilares[i-1]}", 0, 1)
                pdf.AnaliseIA(ss[analise_key])

        buffer = BytesIO()
        pdf.output(buffer)
        return buffer.getvalue()

    except Exception as e:
        st.error(f"Ocorreu um erro crítico ao gerar o PDF: {e}")
        return b''

# ==============================================================================
# FUNÇÕES DE CÁLCULO DE SCORE
# ==============================================================================
def calcular_score_pilar1_lastro_robusto():
    scores_aval_loc = []
    map_cred_aval = {'1ª Linha Nacional': 5, 'Regional Conhecido': 4, 'Pouco Conhecido': 2}
    map_qual_comp = {'Sim': 5, 'Parcialmente': 3, 'Não': 1}
    scores_aval_loc.extend([map_cred_aval[st.session_state.credibilidade_avaliador], map_qual_comp[st.session_state.qualidade_comparaveis]])

    valor_imovel = st.session_state.valor_avaliacao_imovel
    valor_estressado = valor_imovel * (1 - st.session_state.estresse_valor_perc / 100)
    ltv_estressado = (st.session_state.saldo_devedor_credito / valor_estressado) * 100 if valor_estressado > 0 else 999
    if ltv_estressado < 70: scores_aval_loc.append(5)
    elif ltv_estressado < 85: scores_aval_loc.append(3)
    else: scores_aval_loc.append(1)

    fipezap = st.session_state.fipezap_12m
    if fipezap > 7.5: scores_aval_loc.append(5)
    elif fipezap > 0: scores_aval_loc.append(4)
    else: scores_aval_loc.append(2)

    liquidez_dias = st.session_state.liquidez_dias
    if liquidez_dias <= 90: scores_aval_loc.append(5)
    elif liquidez_dias <= 180: scores_aval_loc.append(3)
    else: scores_aval_loc.append(1)

    map_risco_oferta = {'Baixo, bairro consolidado': 5, 'Médio, alguns lançamentos': 3, 'Alto, muitos lançamentos': 1}
    scores_aval_loc.append(map_risco_oferta[st.session_state.risco_oferta])
    score_aval_loc = np.mean(scores_aval_loc) if scores_aval_loc else 1

    scores_fisico = []
    map_adequacao = {'Ideal': 5, 'Adequado': 4, 'Pouco Adequado': 2}
    map_rep_const = {'1ª Linha': 5, 'Média': 3, 'Baixa/Desconhecida': 2}
    map_conserv = {'Novo/Reformado': 5, 'Bom, com manutenção': 4, 'Regular, necessita reparos': 2, 'Ruim': 1}
    scores_fisico.extend([map_adequacao[st.session_state.adequacao_produto], map_rep_const[st.session_state.reputacao_construtora], map_conserv[st.session_state.estado_conservacao]])
    score_fisico = np.mean(scores_fisico) if scores_fisico else 1

    scores_legal = []
    scores_legal.append(5 if st.session_state.analise_dominial_20a else 2)
    scores_legal.append(5 if st.session_state.dividas_propter_rem else 1)
    score_cnds = 1 + len(st.session_state.cnds_verificadas)
    scores_legal.append(min(5, score_cnds))
    map_risco_amb = {'Inexistente': 5, 'Baixo/Gerenciado': 4, 'Requer análise': 2}
    scores_legal.append(map_risco_amb[st.session_state.risco_ambiental_imovel])
    score_legal = np.mean(scores_legal) if scores_legal else 1

    score_final_pilar1 = (score_aval_loc * 0.50) + (score_fisico * 0.25) + (score_legal * 0.25)
    return score_final_pilar1

def calcular_score_pilar2_credito_robusto():
    scores_credito = []
    ltv = st.session_state.ltv_operacao
    if ltv < 50: scores_credito.append(5)
    elif ltv <= 70: scores_credito.append(3)
    else: scores_credito.append(1)

    map_finalidade = {'Financiamento de Aquisição': 5, 'Financiamento à Construção': 3, 'Home Equity': 2}
    scores_credito.append(map_finalidade[st.session_state.finalidade_credito])

    if st.session_state.op_amortizacao == 'SAC': scores_credito.append(5)
    else: scores_credito.append(4)

    score_credito = np.mean(scores_credito) if scores_credito else 1

    scores_devedor = []
    if st.session_state.tipo_lastro_credito == 'Crédito Único':
        if st.session_state.tipo_devedor == 'Pessoa Física':
            renda_mensal = st.session_state.renda_mensal_pf
            dti = (st.session_state.parcela_mensal_pf / renda_mensal) * 100 if renda_mensal > 0 else 999
            if dti <= 30: scores_devedor.append(5)
            elif dti <= 40: scores_devedor.append(3)
            else: scores_devedor.append(1)

            map_score_credito = {'Excelente (>800)': 5, 'Bom (600-800)': 4, 'Regular (400-600)': 2, 'Ruim (<400)': 1}
            scores_devedor.append(map_score_credito[st.session_state.score_credito_devedor])

            map_patrimonio = {'> R$ 1.000.000': 5, 'R$ 250k - R$ 1.000.000': 4, '< R$ 250k': 2}
            scores_devedor.append(map_patrimonio[st.session_state.patrimonio_liquido_pf])
        else:
            dl_ebitda = st.session_state.dl_ebitda_pj
            if dl_ebitda < 2.0: scores_devedor.append(5)
            elif dl_ebitda <= 4.0: scores_devedor.append(3)
            else: scores_devedor.append(1)

            liq_corr = st.session_state.liq_corrente_pj
            if liq_corr > 1.5: scores_devedor.append(5)
            elif liq_corr >= 1.0: scores_devedor.append(3)
            else: scores_devedor.append(1)

            dscr = st.session_state.dscr_pj
            if dscr > 1.5: scores_devedor.append(5)
            elif dscr >= 1.2: scores_devedor.append(3)
            else: scores_devedor.append(1)
    else:
        num_dev = st.session_state.num_devedores
        if num_dev > 50: scores_devedor.append(5)
        elif num_dev > 10: scores_devedor.append(4)
        else: scores_devedor.append(2)

        conc_top5 = st.session_state.concentracao_top5
        if conc_top5 < 30: scores_devedor.append(5)
        elif conc_top5 <= 50: scores_devedor.append(3)
        else: scores_devedor.append(1)

    score_devedor = np.mean(scores_devedor) if scores_devedor else 1

    score_performance = 4.0
    if st.session_state.historico_pagamento != 'Novo, sem histórico de pagamento':
        scores_perf = []
        map_hist_pag = {'Pagamentos em dia por > 12 meses': 5, 'Pagamentos em dia por < 12 meses': 4, 'Com histórico de atrasos': 1}
        scores_perf.append(map_hist_pag[st.session_state.historico_pagamento])

        inad_90d = st.session_state.inadimplencia_90d
        if inad_90d == 0: scores_perf.append(5)
        elif inad_90d <= 2: scores_perf.append(3)
        else: scores_perf.append(1)

        score_performance = np.mean(scores_perf) if scores_perf else 1

    score_final_pilar2 = (score_credito * 0.40) + (score_devedor * 0.40) + (score_performance * 0.20)
    return score_final_pilar2

def calcular_score_pilar3_estrutura_robusto():
    scores_estrutura = []
    map_reputacao = {'Banco de 1ª linha / Emissor especialista': 5, 'Instituição financeira média': 4, 'Securitizadora de nicho': 3, 'Emissor pouco conhecido ou com histórico negativo': 1}
    map_servicer = {'Interna, com alta especialização': 5, 'Externa, 1ª linha': 4, 'Externa, padrão de mercado': 3, 'Servicer com histórico fraco': 1}
    scores_estrutura.extend([map_reputacao[st.session_state.reputacao_emissor], map_servicer[st.session_state.qualidade_servicer]])

    fr_pmts = st.session_state.fundo_reserva_pmts
    if fr_pmts >= 3: score_fr = 5
    elif fr_pmts >= 1: score_fr = 3
    else: score_fr = 1
    if st.session_state.fundo_reserva_regra: score_fr = min(5, score_fr + 1)
    scores_estrutura.append(score_fr)

    map_waterfall = {'Clara e bem definida': 5, 'Padrão de mercado': 4, 'Ambígua ou com brechas': 2}
    scores_estrutura.extend([map_waterfall[st.session_state.clareza_waterfall], (5 if st.session_state.despesas_subordinadas else 3)])

    map_parecer = {'Escritório de 1ª linha': 5, 'Padrão de mercado': 4, 'Limitado ou com ressalvas': 2}
    map_reports = {'Alta, detalhados e frequentes': 5, 'Média, cumpre o mínimo regulatório': 3, 'Baixa, informações inconsistentes': 1}
    map_covenants = {'Fortes, com gatilhos objetivos': 5, 'Padrão de mercado': 3, 'Fracos ou inexistentes': 1}
    scores_estrutura.extend([map_parecer[st.session_state.qualidade_parecer_legal], map_reports[st.session_state.qualidade_relatorios], map_covenants[st.session_state.covenants_operacao]])

    score_estrutura = np.mean(scores_estrutura) if scores_estrutura else 1

    score_performance = 4.0
    if st.session_state.historico_pagamento != 'Novo, sem histórico de pagamento':
        scores_perf = []
        saldo_total = st.session_state.saldo_devedor_credito
        perc_inad = (st.session_state.saldo_inadimplente_90d / saldo_total) * 100 if saldo_total > 0 else 0
        if perc_inad == 0: scores_perf.append(5)
        elif perc_inad <= 3: scores_perf.append(3)
        elif perc_inad <= 7: scores_perf.append(2)
        else: scores_perf.append(1)

        parc_atraso = st.session_state.parcelas_em_atraso_media
        if parc_atraso == 0: scores_perf.append(5)
        elif parc_atraso <= 2: scores_perf.append(3)
        else: scores_perf.append(1)

        map_reneg = {'Sem histórico de renegociação': 5, 'Renegociações pontuais e bem-sucedidas': 4, 'Renegociações recorrentes ou com perdas': 1}
        scores_perf.append(map_reneg[st.session_state.historico_renegociacao])

        score_performance = np.mean(scores_perf) if scores_perf else 1

    peso_estrutura = 0.7 if st.session_state.historico_pagamento == 'Novo, sem histórico de pagamento' else 0.5
    peso_performance = 1 - peso_estrutura

    score_final_pilar3 = (score_estrutura * peso_estrutura) + (score_performance * peso_performance)
    return score_final_pilar3

# ==============================================================================
# FUNÇÕES DE CÁLCULO FINANCEIRO (SEM PILAR 4)
# ==============================================================================

def calcular_spread_credito(rating, duration_anos, op_volume):
    matriz_spread_base = {
        'brAAA(sf)': 1.20, 'brAA(sf)': 1.80, 'brA(sf)': 2.50,
        'brBBB(sf)': 3.30, 'brBB(sf)': 4.20, 'brB(sf)': 6.00,
        'brCCC(sf)': 8.50,
    }
    base_spread = matriz_spread_base.get(rating, 10.00)
    liquidity_premium = 0.30 if op_volume < 5_000_000 else 0.10
    duration_adjustment = (duration_anos - 5) * 0.08
    total_spread = base_spread + liquidity_premium + duration_adjustment
    return max(0.5, total_spread)

# ==============================================================================
# FUNÇÕES DE ANÁLISE COM IA
# ==============================================================================
@st.cache_data
def gerar_analise_ia(nome_pilar, dados_pilar_str):
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Aja como um analista de crédito sênior, especialista em Cédulas de Crédito Imobiliário (CCI) no Brasil.
        Sua tarefa é analisar os dados do pilar '{nome_pilar}' de uma operação de CCI e fornecer uma análise qualitativa concisa em português.
        Estruture sua resposta em "Pontos Positivos" e "Pontos de Atenção".
        Seja direto e foque nos pontos mais relevantes para um investidor.
        **Dados para Análise:**
        ---
        {dados_pilar_str}
        ---
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Erro ao chamar API do Gemini: {e}")
        return "Erro: A chave da API do Gemini (GEMINI_API_KEY) não foi encontrada ou a chamada falhou."

def callback_gerar_analise_p1():
    dados_p1_str = f"""
    - **Avaliação e Localização**:
      - Credibilidade do Avaliador: {st.session_state.credibilidade_avaliador}
      - Qualidade dos Comparáveis no Laudo: {st.session_state.qualidade_comparaveis}
      - Variação FipeZAP (12m): {st.session_state.fipezap_12m}%
      - Liquidez Estimada (dias): {st.session_state.liquidez_dias}
      - Risco de Excesso de Oferta na Região: {st.session_state.risco_oferta}
    - **Características do Ativo**:
      - Adequação do Produto ao Mercado: {st.session_state.adequacao_produto}
      - Reputação da Construtora: {st.session_state.reputacao_construtora}
      - Estado de Conservação: {st.session_state.estado_conservacao}
    - **Due Diligence Legal**:
      - Análise de Cadeia Dominial (20 anos): {'Sim' if st.session_state.analise_dominial_20a else 'Não'}
      - Verificação de Dívidas (Condomínio/IPTU): {'Sim' if st.session_state.dividas_propter_rem else 'Não'}
      - Risco Ambiental: {st.session_state.risco_ambiental_imovel}
    """
    with st.spinner("Analisando o Pilar 1..."):
        st.session_state.analise_p1 = gerar_analise_ia("Pilar 1: Lastro Imobiliário", dados_p1_str)

def callback_gerar_analise_p2():
    dados_p2_str = f"""
    - **Estrutura do Crédito**:
      - LTV da Operação: {st.session_state.ltv_operacao:.2f}%
      - Finalidade do Crédito: {st.session_state.finalidade_credito}
      - Composição do Lastro: {st.session_state.tipo_lastro_credito}
    """
    if st.session_state.tipo_lastro_credito == 'Crédito Único':
        dados_p2_str += f"\n- **Perfil do Devedor ({st.session_state.tipo_devedor})**:"
        if st.session_state.tipo_devedor == 'Pessoa Física':
            renda_mensal = st.session_state.renda_mensal_pf
            dti = (st.session_state.parcela_mensal_pf / renda_mensal) * 100 if renda_mensal > 0 else 0
            dados_p2_str += f"""
              - Comprometimento de Renda (DTI): {dti:.2f}%
              - Score de Crédito: {st.session_state.score_credito_devedor}
              - Patrimônio Líquido: {st.session_state.patrimonio_liquido_pf}"""
        else:
            dados_p2_str += f"""
              - Dívida Líquida/EBITDA: {st.session_state.dl_ebitda_pj}x
              - Liquidez Corrente: {st.session_state.liq_corrente_pj}
              - DSCR: {st.session_state.dscr_pj}x"""
    else:
        dados_p2_str += f"""
    - **Perfil da Carteira**:
      - Número de Devedores: {st.session_state.num_devedores}
      - Concentração nos 5 Maiores: {st.session_state.concentracao_top5}%"""

    if st.session_state.historico_pagamento != 'Novo, sem histórico de pagamento':
        dados_p2_str += f"""
    - **Performance Histórica**:
      - Histórico Geral: {st.session_state.historico_pagamento}
      - Inadimplência (>90d): {st.session_state.inadimplencia_90d}%
      - Maior Atraso Observado: {st.session_state.maior_atraso_hist}"""

    with st.spinner("Analisando o Pilar 2..."):
        st.session_state.analise_p2 = gerar_analise_ia("Pilar 2: Crédito e Devedor", dados_p2_str)

def callback_gerar_analise_p3():
    dados_p3_str = f"""
    - **Estrutura e Proteções**:
      - Reputação do Emissor: {st.session_state.reputacao_emissor}
      - Qualidade do Agente de Cobrança (Servicer): {st.session_state.qualidade_servicer}
      - Fundo de Reserva: {st.session_state.fundo_reserva_pmts} pagamentos
      - Clareza do Waterfall: {st.session_state.clareza_waterfall}
      - Qualidade dos Covenants: {st.session_state.covenants_operacao}
    """
    if st.session_state.historico_pagamento != 'Novo, sem histórico de pagamento':
        saldo_total = st.session_state.saldo_devedor_credito
        perc_inad = (st.session_state.saldo_inadimplente_90d / saldo_total) * 100 if saldo_total > 0 else 0
        dados_p3_str += f"""
    - **Performance Atual (Vigilância)**:
      - Inadimplência (>90d): {perc_inad:.2f}% do saldo devedor
      - Histórico de Renegociação: {st.session_state.historico_renegociacao}
    """
    with st.spinner("Analisando o Pilar 3..."):
        st.session_state.analise_p3 = gerar_analise_ia("Pilar 3: Estrutura da CCI", dados_p3_str)

# ==============================================================================
# CORPO PRINCIPAL DA APLICAÇÃO
# ==============================================================================
st.set_page_config(layout="wide", page_title="Análise e Rating de CCI")
st.title("Plataforma de Análise e Rating de CCI")
st.markdown("Ferramenta para análise de risco de crédito em Cédulas de Crédito Imobiliário (CCI)")
st.divider()

inicializar_session_state()

st.sidebar.title("Gestão da Análise")
st.sidebar.divider()
uploaded_file = st.sidebar.file_uploader("1. Carregar Análise Salva (.json)", type="json")
if st.sidebar.button("2. Carregar Dados", disabled=(uploaded_file is None), use_container_width=True):
    try:
        loaded_state_dict = json.load(uploaded_file)
        for key, value in loaded_state_dict.items():
            if key in ['op_data_emissao', 'op_data_vencimento'] and isinstance(value, str):
                st.session_state[key] = datetime.datetime.strptime(value, '%Y-%m-%d').date()
            else:
                st.session_state[key] = value
        st.session_state.state_initialized_cci = True
        st.sidebar.success("Análise carregada!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar: {e}")

state_to_save = {k: v for k, v in st.session_state.items() if k != 'state_initialized_cci'}
json_string = json.dumps(state_to_save, indent=4, default=str)
file_name = state_to_save.get('op_nome', 'analise_cci').replace(' ', '_') + ".json"
st.sidebar.divider()
st.sidebar.download_button(label="Salvar Análise Atual", data=json_string, file_name=file_name,
                           mime="application/json", use_container_width=True)

# --- DEFINIÇÃO DAS ABAS ---
tab0, tab1, tab2, tab3, tab_prec, tab_res, tab_met = st.tabs([
    "Cadastro", "Pilar I: Lastro Imobiliário", "Pilar II: Crédito e Devedor",
    "Pilar III: Estrutura da CCI", "Precificação", "Resultado", "Metodologia"
])

with tab0:
    st.header("Informações Gerais da Operação")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Nome/Identificação da CCI:", key='op_nome')
        st.number_input("Volume da Operação (R$):", key='op_volume', format="%.2f")
        st.selectbox("Sistema de Amortização:", ["SAC", "Price"], key='op_amortizacao')
        st.date_input("Data de Emissão:", key='op_data_emissao')
    with col2:
        st.text_input("Código/Série:", key='op_codigo')
        c1_taxa, c2_taxa = st.columns([1, 2])
        with c1_taxa: st.selectbox("Indexador:", ["IPCA +", "CDI +", "Pré-fixado"], key='op_indexador')
        with c2_taxa: st.number_input("Taxa (% a.a.):", key='op_taxa', format="%.2f")
        st.number_input("Prazo Remanescente (meses):", key='op_prazo', step=1)
        st.date_input(
            "Data de Vencimento:",
            key='op_data_vencimento',
            min_value=st.session_state.op_data_emissao # Validação adicionada
        )
    st.text_input("Emissor da CCI (Ex: Banco, Securitizadora):", key='op_emissor')

with tab1:
    st.header("Pilar I: Análise do Lastro Imobiliário (Due Diligence)")
    st.markdown("Peso no Scorecard: **45%**")

    with st.expander("Subfator 1: Avaliação e Análise de Localização (Peso 50%)", expanded=True):
        st.subheader("Análise Crítica do Laudo")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.selectbox("Credibilidade do Avaliador:", ['1ª Linha Nacional', 'Regional Conhecido', 'Pouco Conhecido'], key='credibilidade_avaliador')
        with c2:
            st.radio("Qualidade dos Comparáveis:", ["Sim", "Parcialmente", "Não"], key='qualidade_comparaveis')
        with c3:
            st.number_input("Estresse no Valor do Imóvel (%)", min_value=0.0, max_value=50.0, step=1.0, key='estresse_valor_perc')

        st.subheader("Análise de Localização")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input("Índice FipeZAP (Venda 12m, %):", key='fipezap_12m', format="%.2f")
        with c2:
            st.number_input("Tempo Médio Absorção (dias):", key='liquidez_dias')
        with c3:
            st.selectbox("Risco de Excesso de Oferta:", ['Baixo, bairro consolidado', 'Médio, alguns lançamentos', 'Alto, muitos lançamentos'], key='risco_oferta')
        st.text_input("Cidade/Estado para Mapa:", key='cidade_mapa')

    with st.expander("Subfator 2: Características Físicas e Adequação (Peso 25%)"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.selectbox("Tipologia do Imóvel:", ['Residencial (Apartamento/Casa)', 'Comercial (Loja/Sala)', 'Galpão Logístico/Industrial', 'Terreno/Gleba'], key='tipo_imovel')
        with c2:
            st.selectbox("Adequação do produto ao público-alvo:", ['Ideal', 'Adequado', 'Pouco Adequado'], key='adequacao_produto')
        with c3:
            st.selectbox("Reputação da Construtora (se aplicável):", ['1ª Linha', 'Média', 'Baixa/Desconhecida'], key='reputacao_construtora')
        st.selectbox("Estado de Conservação:", ['Novo/Reformado', 'Bom, com manutenção', 'Regular, necessita reparos', 'Ruim'], key='estado_conservacao')

    with st.expander("Subfator 3: Due Diligence Legal e Documental (Peso 25%)"):
        c1, c2 = st.columns(2)
        with c1:
            st.checkbox("Análise de Cadeia Dominial (20 anos) foi realizada?", key='analise_dominial_20a')
            st.checkbox("Verificada a inexistência de dívidas (condomínio/IPTU)?", key='dividas_propter_rem')
        with c2:
            st.multiselect("Certidões Verificadas:",
                          options=["CND do Imóvel (IPTU)", "CND do Devedor", "CNDs dos Vendedores Anteriores", "CNDs da Construtora (se novo)"],
                          key='cnds_verificadas')
        st.selectbox("Risco Ambiental Identificado no Imóvel:", ['Inexistente', 'Baixo/Gerenciado', 'Requer análise'], key='risco_ambiental_imovel')

    if st.button("Calcular Score Robusto do Pilar 1", use_container_width=True):
        st.session_state.scores['pilar1'] = calcular_score_pilar1_lastro_robusto()
        st.session_state.map_data = get_coords(st.session_state.cidade_mapa)
        st.plotly_chart(create_gauge_chart(st.session_state.scores['pilar1'], "Score Ponderado (Pilar 1)"), use_container_width=True)
    if st.session_state.get('map_data') is not None:
        st.map(st.session_state.map_data, zoom=11)

    st.divider()
    st.subheader("🤖 Análise com IA Gemini")
    if st.button("Gerar Análise Qualitativa para o Pilar 1", use_container_width=True, on_click=callback_gerar_analise_p1): pass
    if "analise_p1" in st.session_state:
        with st.container(border=True): st.markdown(st.session_state.analise_p1)

with tab2:
    st.header("Pilar II: Análise do Crédito e do Devedor (Due Diligence)")
    st.markdown("Peso no Scorecard: **40%**")

    with st.expander("Subfator 1: Características e Estrutura do Crédito (Peso 40%)", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1: st.number_input("Valor de Avaliação do Imóvel (R$)", key='valor_avaliacao_imovel', format="%.2f", help="Repetido do Pilar 1 para cálculo do LTV.")
        with c2: st.number_input("Saldo Devedor do Crédito (R$)", key='saldo_devedor_credito', format="%.2f")
        with c3:
            ltv_calc = (st.session_state.saldo_devedor_credito / st.session_state.valor_avaliacao_imovel) * 100 if st.session_state.valor_avaliacao_imovel > 0 else 0
            st.session_state.ltv_operacao = ltv_calc
            st.metric("LTV da Operação", f"{ltv_calc:.2f}%")

        st.selectbox("Finalidade do Crédito:", ['Financiamento de Aquisição', 'Financiamento à Construção', 'Home Equity'], key='finalidade_credito', help="Home Equity geralmente apresenta maior risco.")

    with st.expander("Subfator 2: Perfil do Devedor (Peso 40%)", expanded=True):
        st.radio("Composição do Lastro de Crédito:", ['Crédito Único', 'Carteira de Créditos'], key='tipo_lastro_credito', horizontal=True)
        st.divider()
        if st.session_state.tipo_lastro_credito == 'Crédito Único':
            st.radio("Tipo do Devedor:", ['Pessoa Física', 'Pessoa Jurídica'], key='tipo_devedor', horizontal=True)
            if st.session_state.tipo_devedor == 'Pessoa Física':
                st.subheader("Análise Detalhada: Pessoa Física")
                c1,c2 = st.columns(2)
                with c1:
                    st.number_input("Parcela Mensal do Crédito (R$)", key='parcela_mensal_pf')
                    st.selectbox("Outras Dívidas Relevantes:", ['Nenhuma Relevante', 'Endividamento Moderado', 'Altamente Alavancado'], key='outras_dividas_pf')
                with c2:
                    st.number_input("Renda Mensal Comprovada (R$)", key='renda_mensal_pf')
                    st.selectbox("Patrimônio Líquido Estimado:", ['< R$ 250k', 'R$ 250k - R$ 1.000.000', '> R$ 1.000.000'], key='patrimonio_liquido_pf')
                st.selectbox("Score de Crédito (Serasa/SPC):", ['Excelente (>800)', 'Bom (600-800)', 'Regular (400-600)', 'Ruim (<400)'], key='score_credito_devedor')

            else:
                st.subheader("Análise Detalhada: Pessoa Jurídica")
                c1,c2,c3 = st.columns(3)
                with c1: st.number_input("Dívida Líquida / EBITDA", key='dl_ebitda_pj')
                with c2: st.number_input("Liquidez Corrente", key='liq_corrente_pj')
                with c3: st.number_input("DSCR (FCO/Serviço Dívida)", key='dscr_pj', help="Índice de Cobertura do Serviço da Dívida")

        else:
            st.subheader("Análise da Carteira")
            c1,c2 = st.columns(2)
            with c1: st.number_input("Número de Devedores na Carteira", key='num_devedores', min_value=1, step=1)
            with c2: st.slider("Concentração nos 5 Maiores Devedores (%)", 0.0, 100.0, key='concentracao_top5')

    with st.expander("Subfator 3: Performance do Crédito (Peso 20%)", expanded=True):
        st.selectbox("Histórico de Pagamento do Crédito:", ['Novo, sem histórico de pagamento', 'Pagamentos em dia por < 12 meses', 'Pagamentos em dia por > 12 meses', 'Com histórico de atrasos'], key='historico_pagamento')
        if st.session_state.historico_pagamento != 'Novo, sem histórico de pagamento':
            c1,c2,c3 = st.columns(3)
            with c1: st.number_input("Meses de Pagamento Decorridos", key='meses_decorridos_pgto')
            with c2: st.selectbox("Maior Atraso Histórico:", ['Sem atrasos', '< 30 dias', '30-90 dias', '> 90 dias'], key='maior_atraso_hist')
            with c3: st.number_input("Inadimplência Atual > 90d (%)", key='inadimplencia_90d')

    if st.button("Calcular Score Robusto do Pilar 2", use_container_width=True):
        st.session_state.scores['pilar2'] = calcular_score_pilar2_credito_robusto()
        st.plotly_chart(create_gauge_chart(st.session_state.scores['pilar2'], "Score Ponderado (Pilar 2)"), use_container_width=True)

    st.divider()
    st.subheader("🤖 Análise com IA Gemini")
    if st.button("Gerar Análise Qualitativa para o Pilar 2", use_container_width=True, on_click=callback_gerar_analise_p2): pass
    if "analise_p2" in st.session_state:
        with st.container(border=True): st.markdown(st.session_state.analise_p2)

with tab3:
    st.header("Pilar III: Análise da Estrutura da CCI (Due Diligence)")
    st.markdown("Peso no Scorecard: **15%**")

    with st.expander("Subfator 1: Prestadores de Serviço e Governança", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("Reputação e Solidez do Emissor:", ['Banco de 1ª linha / Emissor especialista', 'Instituição financeira média', 'Securitizadora de nicho', 'Emissor pouco conhecido ou com histórico negativo'], key='reputacao_emissor')
        with c2:
            st.selectbox("Qualidade do Agente de Cobrança (Servicer):", ['Interna, com alta especialização', 'Externa, 1ª linha', 'Externa, padrão de mercado', 'Servicer com histórico fraco'], key='qualidade_servicer')

    with st.expander("Subfator 2: Mecanismos de Proteção Estrutural", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Fundo de Reserva (em nº de pagamentos mensais)", key='fundo_reserva_pmts', min_value=0.0, step=0.5)
            st.checkbox("Despesas da operação são subordinadas ao pagamento do investidor?", key='despesas_subordinadas')
        with c2:
            st.checkbox("Fundo de Reserva possui mecanismo de recomposição obrigatória?", key='fundo_reserva_regra')
            st.selectbox("Clareza da Cascata de Pagamentos (Waterfall):", ['Clara e bem definida', 'Padrão de mercado', 'Ambígua ou com brechas'], key='clareza_waterfall')

    with st.expander("Subfator 3: Qualidade Contratual e Transparência", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("Qualidade do Parecer Legal da Estrutura:", ['Escritório de 1ª linha', 'Padrão de mercado', 'Limitado ou com ressalvas'], key='qualidade_parecer_legal')
            st.selectbox("Qualidade dos Covenants Contratuais:", ['Fortes, com gatilhos objetivos', 'Padrão de mercado', 'Fracos ou inexistentes'], key='covenants_operacao')
        with c2:
            st.selectbox("Qualidade dos Relatórios Periódicos:", ['Alta, detalhados e frequentes', 'Média, cumpre o mínimo regulatório', 'Baixa, informações inconsistentes'], key='qualidade_relatorios')
        st.multiselect("Garantias Adicionais (além da Alienação Fiduciária):",
                       options=["Fiança ou Aval dos sócios", "Cessão de outros recebíveis", "Penhor de aplicações financeiras"],
                       key='garantias_adicionais')

    with st.expander("Subfator 4: Análise de Performance e Inadimplência (Vigilância/Surveillance)", expanded=True):
        st.info("Preencha esta seção para operações em andamento. Para novas operações, os valores padrão podem ser mantidos.")
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Saldo inadimplente (> 90 dias) (R$)", key='saldo_inadimplente_90d')
            saldo_total = st.session_state.saldo_devedor_credito
            perc_inad = (st.session_state.saldo_inadimplente_90d / saldo_total) * 100 if saldo_total > 0 else 0
            st.metric("Inadimplência (> 90d)", f"{perc_inad:.2f}%")
        with c2:
            st.number_input("Nº médio de parcelas em atraso por devedor inadimplente", key='parcelas_em_atraso_media', min_value=0, step=1)
            st.selectbox("Histórico de Renegociação:", ['Sem histórico de renegociação', 'Renegociações pontuais e bem-sucedidas', 'Renegociações recorrentes ou com perdas'], key='historico_renegociacao')

    if st.button("Calcular Score Robusto do Pilar 3", use_container_width=True):
        st.session_state.scores['pilar3'] = calcular_score_pilar3_estrutura_robusto()
        st.plotly_chart(create_gauge_chart(st.session_state.scores['pilar3'], "Score Ponderado (Pilar 3)"), use_container_width=True)
    st.divider()
    st.subheader("🤖 Análise com IA Gemini")
    if st.button("Gerar Análise Qualitativa para o Pilar 3", use_container_width=True, on_click=callback_gerar_analise_p3): pass
    if "analise_p3" in st.session_state:
        with st.container(border=True): st.markdown(st.session_state.analise_p3)

with tab_prec:
    st.header("Precificação Indicativa da CCI")
    if len(st.session_state.scores) < 3: # Alterado de 4 para 3
        st.warning("⬅️ Por favor, calcule os 3 pilares de score para precificar a operação.")
    else:
        st.info("A precificação abaixo é calculada somando um spread de crédito (baseado no rating e duration) a uma taxa de referência (NTN-B).")
        
        st.subheader("Parâmetros de Mercado e Resultado")
        c1, c2, c3 = st.columns(3)
        with c1:
            duration_manual = st.number_input("Macaulay Duration da Operação (Anos)", min_value=0.1, step=0.1, key='precificacao_duration_manual')
        with c2:
            taxa_ntnb_input = st.number_input(f"Taxa da NTN-B ({duration_manual:.2f} anos)", key='precificacao_ntnb', step=0.01)
        with c3:
            cdi_proj_input = st.number_input("Projeção de CDI Anual (%)", key='precificacao_cdi_proj', step=0.1)

        pesos = {'pilar1': 0.45, 'pilar2': 0.40, 'pilar3': 0.15}
        rating_final_calc = ajustar_rating(converter_score_para_rating(sum(st.session_state.scores.get(p, 1) * pesos[p] for p in pesos.keys())), st.session_state.ajuste_final)
        spread_cci = calcular_spread_credito(rating_final_calc, duration_manual, st.session_state.op_volume)
        
        taxa_ntnb_dec = taxa_ntnb_input / 100
        cdi_proj_dec = cdi_proj_input / 100
        inflacao_implicita = ((1 + cdi_proj_dec) / (1 + taxa_ntnb_dec)) - 1 if taxa_ntnb_dec > -1 else 0
        
        taxa_real_cci = taxa_ntnb_dec + (spread_cci / 100)
        taxa_nominal_cci = (1 + taxa_real_cci) * (1 + inflacao_implicita) - 1
        spread_cdi_cci = (taxa_nominal_cci - cdi_proj_dec) * 100

        with st.container(border=True):
            st.markdown(f"<h5>Precificação Indicativa ({rating_final_calc})</h5>", unsafe_allow_html=True)
            st.metric("Spread de Crédito sobre NTN-B", f"{spread_cci:.2f}%")
            st.success(f"**Taxa Indicativa (IPCA): IPCA + {taxa_ntnb_input + spread_cci:.2f}% a.a.**")
            st.info(f"**Taxa Indicativa (CDI): CDI + {spread_cdi_cci:.2f}% a.a.**")

with tab_res:
    st.header("Resultado Final e Atribuição de Rating")
    if len(st.session_state.scores) < 3: # Alterado de 4 para 3
        st.warning("Calcule todos os 3 pilares de score antes de prosseguir.")
    else:
        pesos = {'pilar1': 0.45, 'pilar2': 0.40, 'pilar3': 0.15}
        score_final_ponderado = sum(st.session_state.scores.get(p, 1) * pesos[p] for p in pesos)
        rating_indicado = converter_score_para_rating(score_final_ponderado)

        st.subheader("Scorecard Mestre")
        data = {
            'Pilar de Análise': ['Pilar 1: Lastro Imobiliário', 'Pilar 2: Crédito e Devedor', 'Pilar 3: Estrutura da CCI'],
            'Peso': [f"{p*100:.0f}%" for p in pesos.values()],
            'Pontuação (1-5)': [f"{st.session_state.scores.get(p, 'N/A'):.2f}" for p in pesos.keys()],
            'Score Ponderado': [f"{(st.session_state.scores.get(p, 1) * pesos[p]):.2f}" for p in pesos.keys()]
        }
        df_scores = pd.DataFrame(data).set_index('Pilar de Análise')
        st.table(df_scores)

        c1, c2 = st.columns(2)
        c1.metric("Score Final Ponderado", f"{score_final_ponderado:.2f}")
        c2.metric("Rating Indicado", rating_indicado)
        st.divider()

        st.subheader("Deliberação Final do Comitê de Rating")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.number_input("Ajuste Qualitativo (notches)", value=st.session_state.ajuste_final, min_value=-3, max_value=3, step=1, key='ajuste_final')
            rating_final = ajustar_rating(rating_indicado, st.session_state.ajuste_final)
            st.metric("Rating Final Atribuído", value=rating_final)
        with col2:
            st.text_area("Justificativa e comentários finais:", height=150, key='justificativa_final')

        st.divider()
        st.subheader("⬇️ Download do Relatório")
        pdf_data = gerar_relatorio_pdf(st.session_state)
        st.download_button(
            label="Baixar Relatório em PDF", data=pdf_data,
            file_name=f"Relatorio_CCI_{st.session_state.op_nome.replace(' ', '_')}.pdf",
            mime="application/pdf", use_container_width=True
        )

with tab_met:
    st.header("Metodologia de Rating para CCI")
    st.markdown("Esta metodologia foi desenvolvida para a análise e atribuição de rating a Cédulas de Crédito Imobiliário (CCI).")

    st.subheader("1. Arquitetura do Rating: 3 Pilares Ponderados")
    st.markdown("""
    - **Pilar I: Análise do Lastro Imobiliário (Peso: 45%)**
    - **Pilar II: Análise do Crédito e do Devedor (Peso: 40%)**
    - **Pilar III: Análise da Estrutura da Operação (Peso: 15%)**
    """)

    with st.expander("Pilar I: Risco do Lastro Imobiliário (Peso: 45%)"):
        st.markdown("Avalia a qualidade e a liquidez da garantia real através de uma due diligence aprofundada, dividida em subfatores ponderados: Avaliação e Localização (50%), Características Físicas (25%) e Due Diligence Legal (25%).")

    with st.expander("Pilar II: Risco do Crédito e do Devedor (Peso: 40%)"):
        st.markdown("""
        Avalia a capacidade e a disposição do devedor em honrar o fluxo de pagamentos. A análise é modular e ponderada em três subfatores: Características do Crédito (40%), Perfil do Devedor (40%) e Performance (20%). A análise do devedor se adapta para cenários de Devedor Único (PF ou PJ) ou Carteira de Créditos.
        """)

    with st.expander("Pilar III: Estrutura da CCI (Peso: 15%)"):
        st.markdown("""
        Analisa os mecanismos legais, financeiros e operacionais que protegem o investidor. A análise é dividida em dois componentes principais com pesos dinâmicos:
        - **Análise Estrutural (Peso 70% para ops novas):** Avalia a qualidade dos prestadores (Emissor, Servicer), os mecanismos de proteção (Fundo de Reserva, Waterfall) e a robustez dos contratos.
        - **Análise de Performance (Peso 30% para ops novas):** Módulo de vigilância que mede a saúde real do crédito através de métricas de inadimplência e renegociações. O peso deste componente aumenta para operações com maior histórico.
        """)
