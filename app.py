# app_cci.py
import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import datetime
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

        defaults = {
            # --- Chaves para a aba de Cadastro ---
            'op_nome': 'CCI Exemplo Residencial', 'op_codigo': 'CCIEX123',
            'op_emissor': 'Banco Exemplo S.A.', 'op_volume': 1500000.0,
            'op_taxa': 11.5, 'op_indexador': 'IPCA +', 'op_prazo': 240,
            'op_amortizacao': 'SAC', 'op_data_emissao': datetime.date(2024, 5, 1),
            'op_data_vencimento': datetime.date(2044, 5, 1),

            # --- PILAR 1: Lastro Imobiliário ---
            'laudo_recente': 'Sim, < 6 meses', 'metodologia_laudo': 'Comparativo de Mercado',
            'liquidez_forcada_perc': 80.0, 'qualidade_localizacao': 'Bairro nobre, alta liquidez',
            'vetor_crescimento': 'Estável / Consolidado', 'cidade_mapa': 'São Paulo, SP',
            'tipo_imovel': 'Residencial (Apartamento/Casa)', 'estagio_imovel': 'Pronto e averbado',
            'padrao_construtivo': 'Luxo/Alto Padrão', 'regularidade_matricula': 'Sim, sem ônus relevantes',
            'habitese_regular': True,

            # --- PILAR 2: Crédito e Devedor ---
            'valor_avaliacao_imovel': 2500000.0, 'saldo_devedor_credito': 1500000.0,
            'ltv_operacao': 60.0, 'tipo_devedor': 'Pessoa Física',
            'score_credito_devedor': 'Excelente (>800)', 'comprometimento_renda': 'Abaixo de 30%',
            'estabilidade_renda': 'Alta (Ex: Servidor Público, funcionário de grande empresa)',
            'saude_financeira_pj': 'Robusta (baixo endividamento, alta lucratividade)',
            'historico_pagamento': 'Novo, sem histórico de pagamento',
            'prazo_remanescente_credito': 240,

            # --- PILAR 3: Estrutura da CCI ---
            'reputacao_emissor': 'Banco de 1ª linha / Emissor especialista',
            'regime_fiduciario': 'Sim',
            'garantias_adicionais': [],
            'seguros_mip_dfi': 'Sim, apólices vigentes e adequadas',
            'covenants_operacao': 'Fortes, com gatilhos objetivos',

            # --- PILAR 4: Cenário de Mercado ---
            'ambiente_juros': 'Juros altos / Restritivo',
            'tendencia_setor': 'Estável com viés de alta',
            'liquidez_mercado': 'Média / Seletiva',
            'ambiente_regulatorio': 'Estável',

            # --- Precificação e Resultado ---
            'precificacao_ntnb': 6.15,
            'precificacao_cdi_proj': 10.25,
            'ajuste_final': 0,
            'justificativa_final': '',
            'modelagem_yield': 11.5
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

@st.cache_data
def get_coords(city):
    # (Função mantida como no original)
    if not city: return None
    try:
        geolocator = Nominatim(user_agent="cci_analyzer_app")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        location = geocode(city)
        if location: return pd.DataFrame({'lat': [location.latitude], 'lon': [location.longitude]})
    except Exception: return None

def create_gauge_chart(score, title):
    # (Função mantida como no original)
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
    # (Função mantida como no original)
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
    # (Função mantida como no original)
    escala = ['brD(sf)', 'brC(sf)','brCC(sf)','brCCC(sf)', 'brB(sf)', 'brBB(sf)', 'brBBB(sf)', 'brA(sf)', 'brAA(sf)', 'brAAA(sf)']
    try:
        idx_base = escala.index(rating_base)
        idx_final = max(0, min(len(escala) - 1, idx_base + notches))
        return escala[idx_final]
    except (ValueError, TypeError): return rating_base

class PDF(FPDF):
    # (Classe PDF mantida, com pequenas adaptações nas tabelas)
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
            ["Pilar 4: Cenário de Mercado", f"{pesos['pilar4']*100:.0f}%", f"{ss.scores.get('pilar4', 0):.2f}", f"{ss.scores.get('pilar4', 0) * pesos['pilar4']:.2f}"],
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

        pesos_cci = {'pilar1': 0.40, 'pilar2': 0.35, 'pilar3': 0.15, 'pilar4': 0.10}
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
        nomes_pilares = ["Lastro Imobiliário", "Crédito e Devedor", "Estrutura da CCI", "Cenário de Mercado"]
        for i in range(1, 5):
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
# FUNÇÕES DE CÁLCULO DE SCORE (LÓGICA INVERTIDA: 5 = MELHOR, 1 = PIOR)
# ==============================================================================
def calcular_score_pilar1_lastro():
    scores = []
    # Fator 1: Avaliação e Localização
    map_laudo = {'Sim, < 6 meses': 5, 'Sim, entre 6 e 12 meses': 4, 'Não ou > 12 meses': 1}
    map_metodologia = {'Comparativo de Mercado': 5, 'Renda ou Custo de Reposição': 3}
    map_localizacao = {'Bairro nobre, alta liquidez': 5, 'Bairro bom, boa liquidez': 4, 'Região mediana': 3, 'Região periférica/Baixa liquidez': 1}
    map_vetor = {'Forte valorização': 5, 'Estável / Consolidado': 4, 'Estagnado ou em declínio': 2}
    scores.extend([map_laudo[st.session_state.laudo_recente], map_metodologia[st.session_state.metodologia_laudo],
                   map_localizacao[st.session_state.qualidade_localizacao], map_vetor[st.session_state.vetor_crescimento]])
    if st.session_state.liquidez_forcada_perc >= 80: scores.append(5)
    elif st.session_state.liquidez_forcada_perc >= 70: scores.append(3)
    else: scores.append(1)
    
    # Fator 2: Características e Documentação
    map_tipo_imovel = {'Residencial (Apartamento/Casa)': 5, 'Comercial (Loja/Sala)': 4, 'Galpão Logístico/Industrial': 3, 'Terreno/Gleba': 1}
    map_estagio = {'Pronto e averbado': 5, 'Pronto, pendente Habite-se': 3, 'Em construção avançada (>80%)': 2, 'Em construção inicial': 1}
    map_padrao = {'Luxo/Alto Padrão': 5, 'Médio Padrão': 4, 'Padrão Econômico': 3}
    map_matricula = {'Sim, sem ônus relevantes': 5, 'Sim, com ônus gerenciáveis': 3, 'Não ou com ônus impeditivos': 1}
    scores.extend([map_tipo_imovel[st.session_state.tipo_imovel], map_estagio[st.session_state.estagio_imovel],
                   map_padrao[st.session_state.padrao_construtivo], map_matricula[st.session_state.regularidade_matricula],
                   (5 if st.session_state.habitese_regular else 2)])
                   
    return np.mean(scores) if scores else 1

def calcular_score_pilar2_credito():
    scores = []
    # Fator 1: Métricas de Crédito
    ltv = st.session_state.ltv_operacao
    if ltv < 50: scores.append(5)
    elif ltv <= 70: scores.append(3)
    else: scores.append(1)
    
    map_comprometimento = {'Abaixo de 30%': 5, 'Entre 30% e 40%': 3, 'Acima de 40%': 1, 'Não Aplicável (PJ)': 4}
    scores.append(map_comprometimento[st.session_state.comprometimento_renda])
    
    map_historico = {'Pagamentos em dia por > 12 meses': 5, 'Pagamentos em dia por < 12 meses': 4, 'Novo, sem histórico de pagamento': 3, 'Com histórico de atrasos': 1}
    scores.append(map_historico[st.session_state.historico_pagamento])
    
    # Fator 2: Perfil do Devedor
    map_score_credito = {'Excelente (>800)': 5, 'Bom (600-800)': 4, 'Regular (400-600)': 2, 'Ruim (<400)': 1, 'Não Aplicável (PJ)': 4}
    map_estabilidade_renda = {'Alta (Ex: Servidor Público, funcionário de grande empresa)': 5, 'Média (Ex: Profissional liberal estabelecido)': 4, 'Baixa (Ex: Autônomo, renda variável)': 2}
    map_saude_pj = {'Robusta (baixo endividamento, alta lucratividade)': 5, 'Moderada (endividamento gerenciável)': 3, 'Frágil (alavancada, baixa lucratividade)': 1}

    if st.session_state.tipo_devedor == 'Pessoa Física':
        scores.extend([map_score_credito[st.session_state.score_credito_devedor], map_estabilidade_renda[st.session_state.estabilidade_renda]])
    else: # Pessoa Jurídica
        scores.append(map_saude_pj[st.session_state.saude_financeira_pj])
        
    return np.mean(scores) if scores else 1

def calcular_score_pilar3_estrutura():
    scores = []
    map_reputacao = {'Banco de 1ª linha / Emissor especialista': 5, 'Instituição financeira média': 4, 'Securitizadora de nicho': 3, 'Emissor pouco conhecido ou com histórico negativo': 1}
    scores.append(map_reputacao[st.session_state.reputacao_emissor])
    scores.append(5 if st.session_state.regime_fiduciario else 1)
    
    map_seguros = {'Sim, apólices vigentes e adequadas': 5, 'Sim, mas com ressalvas ou cobertura parcial': 3, 'Não ou apólices inadequadas': 1}
    scores.append(map_seguros[st.session_state.seguros_mip_dfi])
    
    map_covenants = {'Fortes, com gatilhos objetivos': 5, 'Padrão de mercado': 3, 'Fracos ou inexistentes': 1}
    scores.append(map_covenants[st.session_state.covenants_operacao])
    
    # Bônus por garantias adicionais
    score_base = np.mean(scores)
    bonus = len(st.session_state.garantias_adicionais) * 0.25
    return min(5.0, score_base + bonus)

def calcular_score_pilar4_cenario():
    scores = []
    map_juros = {'Juros baixos / Expansionista': 5, 'Juros estáveis / Neutro': 4, 'Juros altos / Restritivo': 2}
    map_setor = {'Aquecido com forte valorização': 5, 'Estável com viés de alta': 4, 'Estagnado ou com viés de baixa': 2}
    map_liquidez = {'Alta / Vários compradores': 5, 'Média / Seletiva': 3, 'Baixa / Poucos negócios': 1}
    map_regulatorio = {'Estável': 5, 'Com pequenas mudanças previstas': 4, 'Com mudanças relevantes em discussão': 2}
    scores.extend([map_juros[st.session_state.ambiente_juros], map_setor[st.session_state.tendencia_setor],
                   map_liquidez[st.session_state.liquidez_mercado], map_regulatorio[st.session_state.ambiente_regulatorio]])
    return np.mean(scores) if scores else 1

# ==============================================================================
# FUNÇÕES DE GERAÇÃO DE FLUXO E CÁLCULO FINANCEIRO
# ==============================================================================

def gerar_fluxo_cci(ss):
    """Gera um fluxo de caixa simplificado para a CCI, baseado no sistema de amortização."""
    try:
        saldo_devedor = ss.op_volume
        taxa_aa = ss.op_taxa / 100
        prazo_meses = int(ss.op_prazo)
        amortizacao_tipo = ss.op_amortizacao
        
        # Assume que a taxa da CCI é real (IPCA +) e usa-a para o fluxo real.
        taxa_am = (1 + taxa_aa)**(1/12) - 1
        
        fluxo, saldo_atual = [], saldo_devedor
        
        for mes in range(1, prazo_meses + 1):
            if saldo_atual <= 0.01: break
            
            juros = saldo_atual * taxa_am
            
            if amortizacao_tipo == 'Price':
                pmt = npf.pmt(taxa_am, prazo_meses - mes + 1, -saldo_atual) if taxa_am > 0 else saldo_devedor / prazo_meses
                principal = pmt - juros
            else: # SAC
                principal = saldo_devedor / prazo_meses
            
            principal = min(principal, saldo_atual)
            pagamento_total = principal + juros
            
            fluxo.append({
                "Mês": mes, "Juros": juros, "Amortização": principal,
                "Pagamento Total": pagamento_total, "Saldo Devedor": saldo_atual - principal
            })
            saldo_atual -= principal
            
        return pd.DataFrame(fluxo)
    except Exception as e:
        st.error(f"Erro ao gerar fluxo da CCI: {e}")
        return pd.DataFrame()

def calcular_duration(df_fluxo, coluna_fluxo, taxa_yield_anual):
    """ (Função mantida como no original) """
    try:
        if coluna_fluxo not in df_fluxo.columns:
            st.error(f"Erro: a coluna '{coluna_fluxo}' não foi encontrada.")
            return 0.0
        taxa_yield_mensal = (1 + taxa_yield_anual / 100)**(1/12) - 1
        soma_pv_fluxos = sum(cf / (1 + taxa_yield_mensal)**t for t, cf in zip(df_fluxo['Mês'], df_fluxo[coluna_fluxo]))
        if soma_pv_fluxos == 0: return 0.0
        soma_pv_ponderado_tempo = sum((t) * cf / (1 + taxa_yield_mensal)**t for t, cf in zip(df_fluxo['Mês'], df_fluxo[coluna_fluxo]))
        duration_meses = soma_pv_ponderado_tempo / soma_pv_fluxos
        return duration_meses / 12
    except Exception as e:
        st.error(f"Erro ao calcular o Duration: {e}")
        return 0.0

def calcular_spread_credito(rating, duration_anos, op_volume):
    """Calcula um spread de crédito para CCI."""
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
    except Exception:
        return "Erro: A chave da API do Gemini (GEMINI_API_KEY) não foi encontrada."


def callback_gerar_analise_p1():
    dados_p1_str = f"- Qualidade da Localização: {st.session_state.qualidade_localizacao}\n- Qualidade do Imóvel: {st.session_state.tipo_imovel} - {st.session_state.padrao_construtivo}\n- Atualização do Laudo: {st.session_state.laudo_recente}\n- Situação Legal: Matrícula {st.session_state.regularidade_matricula}, Habite-se {st.session_state.habitese_regular}"
    with st.spinner("Analisando o Pilar 1..."):
        st.session_state.analise_p1 = gerar_analise_ia("Pilar 1: Lastro Imobiliário", dados_p1_str)

def callback_gerar_analise_p2():
    dados_p2_str = f"- LTV da Operação: {st.session_state.ltv_operacao:.2f}%\n- Perfil do Devedor: {st.session_state.tipo_devedor}\n- Score de Crédito (PF): {st.session_state.score_credito_devedor}\n- Comprometimento de Renda (PF): {st.session_state.comprometimento_renda}\n- Saúde Financeira (PJ): {st.session_state.saude_financeira_pj}\n- Histórico de Pagamento: {st.session_state.historico_pagamento}"
    with st.spinner("Analisando o Pilar 2..."):
        st.session_state.analise_p2 = gerar_analise_ia("Pilar 2: Crédito e Devedor", dados_p2_str)

def callback_gerar_analise_p3():
    dados_p3_str = f"- Reputação do Emissor: {st.session_state.reputacao_emissor}\n- Segregação de Risco: Regime Fiduciário {'Sim' if st.session_state.regime_fiduciario else 'Não'}\n- Seguros Obrigatórios: {st.session_state.seguros_mip_dfi}\n- Garantias Adicionais: {', '.join(st.session_state.garantias_adicionais) if st.session_state.garantias_adicionais else 'Nenhuma'}"
    with st.spinner("Analisando o Pilar 3..."):
        st.session_state.analise_p3 = gerar_analise_ia("Pilar 3: Estrutura da CCI", dados_p3_str)

def callback_gerar_analise_p4():
    dados_p4_str = f"- Ambiente de Juros: {st.session_state.ambiente_juros}\n- Tendência do Setor Imobiliário: {st.session_state.tendencia_setor}\n- Liquidez de Mercado para o Ativo: {st.session_state.liquidez_mercado}"
    with st.spinner("Analisando o Pilar 4..."):
        st.session_state.analise_p4 = gerar_analise_ia("Pilar 4: Cenário de Mercado", dados_p4_str)

# ==============================================================================
# CORPO PRINCIPAL DA APLICAÇÃO
# ==============================================================================
st.set_page_config(layout="wide", page_title="Análise e Rating de CCI")
st.title("Plataforma de Análise e Rating de CCI")
st.markdown("Ferramenta para análise de risco de crédito em Cédulas de Crédito Imobiliário (CCI)")
st.divider()

inicializar_session_state()

# --- BLOCO DE SALVAR/CARREGAR ---
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
tab0, tab1, tab2, tab3, tab4, tab_prec, tab_res, tab_met = st.tabs([
    "Cadastro", "Pilar I: Lastro Imobiliário", "Pilar II: Crédito e Devedor",
    "Pilar III: Estrutura da CCI", "Pilar IV: Cenário de Mercado",
    "Precificação", "Resultado", "Metodologia"
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
        st.date_input("Data de Vencimento:", key='op_data_vencimento')
    st.text_input("Emissor da CCI (Ex: Banco, Securitizadora):", key='op_emissor')

with tab1:
    st.header("Pilar I: Análise do Lastro Imobiliário")
    st.markdown("Peso no Scorecard: **40%**")
    with st.expander("Fator 1: Avaliação e Localização (Peso 50%)", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("Laudo de avaliação é recente?", ['Sim, < 6 meses', 'Sim, entre 6 e 12 meses', 'Não ou > 12 meses'], key='laudo_recente')
            st.selectbox("Qualidade da localização:", ['Bairro nobre, alta liquidez', 'Bairro bom, boa liquidez', 'Região mediana', 'Região periférica/Baixa liquidez'], key='qualidade_localizacao')
            st.text_input("Cidade/Estado para Mapa:", key='cidade_mapa')
        with c2:
            st.selectbox("Metodologia do laudo é adequada?", ['Comparativo de Mercado', 'Renda ou Custo de Reposição'], key='metodologia_laudo')
            st.selectbox("Vetor de crescimento da região:", ['Forte valorização', 'Estável / Consolidado', 'Estagnado ou em declínio'], key='vetor_crescimento')
            st.slider("Deságio para liquidez forçada (%)", 50.0, 100.0, key='liquidez_forcada_perc', format="%.1f%%")
    with st.expander("Fator 2: Características Físicas e Documentais (Peso 50%)"):
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("Tipologia do Imóvel:", ['Residencial (Apartamento/Casa)', 'Comercial (Loja/Sala)', 'Galpão Logístico/Industrial', 'Terreno/Gleba'], key='tipo_imovel')
            st.selectbox("Padrão Construtivo:", ['Luxo/Alto Padrão', 'Médio Padrão', 'Padrão Econômico'], key='padrao_construtivo')
            st.checkbox("Possui Habite-se regularizado?", key='habitese_regular')
        with c2:
            st.selectbox("Estágio do Imóvel:", ['Pronto e averbado', 'Pronto, pendente Habite-se', 'Em construção avançada (>80%)', 'Em construção inicial'], key='estagio_imovel')
            st.selectbox("Matrícula do imóvel está regular?", ['Sim, sem ônus relevantes', 'Sim, com ônus gerenciáveis', 'Não ou com ônus impeditivos'], key='regularidade_matricula')

    if st.button("Calcular Score e Mapa do Pilar 1", use_container_width=True):
        st.session_state.scores['pilar1'] = calcular_score_pilar1_lastro()
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
    st.header("Pilar II: Análise do Crédito e do Devedor")
    st.markdown("Peso no Scorecard: **35%**")
    with st.expander("Fator 1: Métricas de Crédito (Peso 50%)", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1: st.number_input("Valor de Avaliação do Imóvel (R$)", key='valor_avaliacao_imovel', format="%.2f")
        with c2: st.number_input("Saldo Devedor do Crédito (R$)", key='saldo_devedor_credito', format="%.2f")
        with c3:
            ltv_calc = (st.session_state.saldo_devedor_credito / st.session_state.valor_avaliacao_imovel) * 100 if st.session_state.valor_avaliacao_imovel > 0 else 0
            st.session_state.ltv_operacao = ltv_calc
            st.metric("LTV Calculado", f"{ltv_calc:.2f}%")
        st.selectbox("Histórico de Pagamento do Crédito:", ['Novo, sem histórico de pagamento', 'Pagamentos em dia por < 12 meses', 'Pagamentos em dia por > 12 meses', 'Com histórico de atrasos'], key='historico_pagamento')
    with st.expander("Fator 2: Perfil do Devedor (Peso 50%)"):
        st.radio("Tipo do Devedor:", ['Pessoa Física', 'Pessoa Jurídica'], key='tipo_devedor', horizontal=True)
        if st.session_state.tipo_devedor == 'Pessoa Física':
            st.selectbox("Score de Crédito (Serasa/SPC):", ['Excelente (>800)', 'Bom (600-800)', 'Regular (400-600)', 'Ruim (<400)'], key='score_credito_devedor')
            st.selectbox("Comprometimento de Renda (Parcela/Renda):", ['Abaixo de 30%', 'Entre 30% e 40%', 'Acima de 40%'], key='comprometimento_renda')
            st.selectbox("Estabilidade da Fonte de Renda:", ['Alta (Ex: Servidor Público, funcionário de grande empresa)', 'Média (Ex: Profissional liberal estabelecido)', 'Baixa (Ex: Autônomo, renda variável)'], key='estabilidade_renda')
        else:
            st.selectbox("Saúde Financeira da Empresa (PJ):", ['Robusta (baixo endividamento, alta lucratividade)', 'Moderada (endividamento gerenciável)', 'Frágil (alavancada, baixa lucratividade)'], key='saude_financeira_pj')

    if st.button("Calcular Score do Pilar 2", use_container_width=True):
        st.session_state.scores['pilar2'] = calcular_score_pilar2_credito()
        st.plotly_chart(create_gauge_chart(st.session_state.scores['pilar2'], "Score Ponderado (Pilar 2)"), use_container_width=True)

    st.divider()
    st.subheader("🤖 Análise com IA Gemini")
    if st.button("Gerar Análise Qualitativa para o Pilar 2", use_container_width=True, on_click=callback_gerar_analise_p2): pass
    if "analise_p2" in st.session_state:
        with st.container(border=True): st.markdown(st.session_state.analise_p2)

with tab3:
    st.header("Pilar III: Análise da Estrutura da CCI")
    st.markdown("Peso no Scorecard: **15%**")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Reputação e Solidez do Emissor:", ['Banco de 1ª linha / Emissor especialista', 'Instituição financeira média', 'Securitizadora de nicho', 'Emissor pouco conhecido ou com histórico negativo'], key='reputacao_emissor')
        st.selectbox("Qualidade dos Covenants Contratuais:", ['Fortes, com gatilhos objetivos', 'Padrão de mercado', 'Fracos ou inexistentes'], key='covenants_operacao')
    with c2:
        st.checkbox("Operação submetida a Regime Fiduciário?", key='regime_fiduciario')
        st.selectbox("Seguros MIP e DFI:", ['Sim, apólices vigentes e adequadas', 'Sim, mas com ressalvas ou cobertura parcial', 'Não ou apólices inadequadas'], key='seguros_mip_dfi')
    st.multiselect("Garantias Adicionais (além da Alienação Fiduciária do Imóvel):",
                   options=["Fiança ou Aval dos sócios", "Cessão de outros recebíveis", "Penhor de aplicações financeiras"],
                   key='garantias_adicionais')

    if st.button("Calcular Score do Pilar 3", use_container_width=True):
        st.session_state.scores['pilar3'] = calcular_score_pilar3_estrutura()
        st.plotly_chart(create_gauge_chart(st.session_state.scores['pilar3'], "Score Ponderado (Pilar 3)"), use_container_width=True)
    st.divider()
    st.subheader("🤖 Análise com IA Gemini")
    if st.button("Gerar Análise Qualitativa para o Pilar 3", use_container_width=True, on_click=callback_gerar_analise_p3): pass
    if "analise_p3" in st.session_state:
        with st.container(border=True): st.markdown(st.session_state.analise_p3)

with tab4:
    st.header("Pilar IV: Análise do Cenário Macroeconômico e Setorial")
    st.markdown("Peso no Scorecard: **10%**")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Ambiente de Taxa de Juros (Selic):", ['Juros baixos / Expansionista', 'Juros estáveis / Neutro', 'Juros altos / Restritivo'], key='ambiente_juros')
        st.selectbox("Liquidez de Mercado para o tipo de ativo:", ['Alta / Vários compradores', 'Média / Seletiva', 'Baixa / Poucos negócios'], key='liquidez_mercado')
    with c2:
        st.selectbox("Tendência do Setor Imobiliário (específico do ativo):", ['Aquecido com forte valorização', 'Estável com viés de alta', 'Estagnado ou com viés de baixa'], key='tendencia_setor')
        st.selectbox("Ambiente Legal e Regulatório:", ['Estável', 'Com pequenas mudanças previstas', 'Com mudanças relevantes em discussão'], key='ambiente_regulatorio')

    if st.button("Calcular Score do Pilar 4", use_container_width=True):
        st.session_state.scores['pilar4'] = calcular_score_pilar4_cenario()
        st.plotly_chart(create_gauge_chart(st.session_state.scores['pilar4'], "Score Ponderado (Pilar 4)"), use_container_width=True)
    st.divider()
    st.subheader("🤖 Análise com IA Gemini")
    if st.button("Gerar Análise Qualitativa para o Pilar 4", use_container_width=True, on_click=callback_gerar_analise_p4): pass
    if "analise_p4" in st.session_state:
        with st.container(border=True): st.markdown(st.session_state.analise_p4)

with tab_prec:
    st.header("Precificação Indicativa da CCI")
    if len(st.session_state.scores) < 4:
        st.warning("⬅️ Por favor, calcule os 4 pilares de score para precificar a operação.")
    else:
        st.info("A precificação abaixo é calculada somando um spread de crédito (baseado no rating e duration) a uma taxa de referência (NTN-B).")
        st.subheader("Geração do Fluxo de Caixa e Cálculo do Duration")

        if st.button("Gerar Fluxo e Calcular Duration", use_container_width=True):
            st.session_state.fluxo_cci_df = gerar_fluxo_cci(st.session_state)
        
        if not st.session_state.fluxo_cci_df.empty:
            df = st.session_state.fluxo_cci_df
            st.line_chart(df.set_index('Mês')[['Juros', 'Amortização']])
            st.line_chart(df.set_index('Mês')[['Saldo Devedor']])
            
            duration_op = calcular_duration(df, 'Pagamento Total', st.session_state.modelagem_yield)
            st.metric("Macaulay Duration Calculada", f"{duration_op:.2f} anos")
            st.divider()

            st.subheader("Parâmetros de Mercado e Resultado")
            c1, c2 = st.columns(2)
            with c1:
                taxa_ntnb_input = st.number_input(f"Taxa da NTN-B ({duration_op:.2f} anos)", key='precificacao_ntnb', step=0.01)
            with c2:
                cdi_proj_input = st.number_input("Projeção de CDI Anual (%)", key='precificacao_cdi_proj', step=0.1)

            rating_final_calc = ajustar_rating(converter_score_para_rating(sum(st.session_state.scores.get(p, 1) * w for p, w in {'pilar1': 0.4, 'pilar2': 0.35, 'pilar3': 0.15, 'pilar4': 0.1}.items())), st.session_state.ajuste_final)
            spread_cci = calcular_spread_credito(rating_final_calc, duration_op, st.session_state.op_volume)
            
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
        else:
            st.info("Clique no botão acima para gerar o fluxo de caixa da CCI e calcular seu duration.")


with tab_res:
    st.header("Resultado Final e Atribuição de Rating")
    if len(st.session_state.scores) < 4:
        st.warning("Calcule todos os 4 pilares de score antes de prosseguir.")
    else:
        pesos = {'pilar1': 0.40, 'pilar2': 0.35, 'pilar3': 0.15, 'pilar4': 0.10}
        score_final_ponderado = sum(st.session_state.scores.get(p, 1) * pesos[p] for p in pesos)
        rating_indicado = converter_score_para_rating(score_final_ponderado)

        st.subheader("Scorecard Mestre")
        data = {
            'Pilar de Análise': ['Pilar 1: Lastro Imobiliário', 'Pilar 2: Crédito e Devedor', 'Pilar 3: Estrutura da CCI', 'Pilar 4: Cenário de Mercado'],
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
    st.markdown("""
    Esta metodologia foi desenvolvida para a análise e atribuição de rating a Cédulas de Crédito Imobiliário (CCI), títulos de crédito com lastro em um crédito imobiliário específico.
    """)

    st.subheader("1. Arquitetura do Rating: 4 Pilares Ponderados")
    st.markdown("""
    A análise é dividida em quatro pilares principais. A ponderação reflete a importância de cada componente de risco para uma CCI.

    - **Pilar I: Análise do Lastro Imobiliário (Peso: 40%)**
    - **Pilar II: Análise do Crédito e do Devedor (Peso: 35%)**
    - **Pilar III: Análise da Estrutura da Operação (Peso: 15%)**
    - **Pilar IV: Análise do Cenário Macroeconômico e Setorial (Peso: 10%)**

    Cada pilar recebe uma pontuação de 1 (pior) a 5 (melhor), que é então ponderada para gerar um score final.
    """)

    with st.expander("Pilar I: Risco do Lastro Imobiliário (Peso: 40%)"):
        st.markdown("""
        Avalia a qualidade e a liquidez da garantia real, que é a principal fonte de recuperação do crédito em caso de inadimplência.
        - **Fatores Analisados:** Qualidade e recentidade do laudo de avaliação, localização e liquidez da região, tipologia e padrão do imóvel, e regularidade da documentação (matrícula, habite-se).
        """)

    with st.expander("Pilar II: Risco do Crédito e do Devedor (Peso: 35%)"):
        st.markdown("""
        Avalia a capacidade e a disposição do devedor em honrar o fluxo de pagamentos, a primeira linha de defesa do investidor.
        - **Fatores Analisados:** Loan-to-Value (LTV) da operação, perfil do devedor (PF ou PJ), score de crédito, comprometimento de renda (PF), saúde financeira (PJ) e histórico de pagamento.
        """)

    with st.expander("Pilar III: Estrutura da CCI (Peso: 15%)"):
        st.markdown("""
        Analisa os mecanismos legais e financeiros que protegem o investidor da CCI.
        - **Fatores Analisados:** Reputação e solidez do emissor, existência de regime fiduciário, presença de garantias adicionais (além da alienação fiduciária), qualidade dos seguros obrigatórios (MIP/DFI) e robustez dos covenants.
        """)
        
    with st.expander("Pilar IV: Cenário de Mercado (Peso: 10%)"):
        st.markdown("""
        Contextualiza a operação dentro do ambiente de mercado, avaliando riscos sistêmicos que podem afetar o devedor e o valor do imóvel.
        - **Fatores Analisados:** Ambiente de juros (Selic), tendências do setor imobiliário específico, liquidez de mercado para o tipo de ativo e estabilidade do ambiente regulatório.
        """)
