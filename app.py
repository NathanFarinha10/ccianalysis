import streamlit as st
import pandas as pd
import datetime
import os

# --- Configuração da Página ---
st.set_page_config(
    page_title="Plataforma de Rating - CCI",
    page_icon="🏠",
    layout="wide"
)

# --- Título e Descrição ---
st.title("Plataforma de Rating para Cédulas de Crédito Imobiliário (CCI)")
st.markdown("Ferramenta para análise e atribuição de rating de risco de crédito para operações de CCI, baseada em metodologia multidimensional.")

# --- Inicialização do Session State ---
# Usamos o session state para manter os dados inseridos pelo usuário entre as abas
if 'inputs' not in st.session_state:
    st.session_state.inputs = {
        'info_gerais': {},
        'pilar1': {},
        'pilar2': {},
        'pilar3_4': {},
        'resultado': {}
    }

# --- Funções de Cálculo do Rating ---

def calcular_score_pilar1(inputs):
    """Calcula o score para o Pilar I: Análise do Lastro Imobiliário."""
    score = 0
    
    # LTV Implícito do Lastro (Valor do Imóvel / Dívida)
    # LTV < 50% é excelente, > 70% é arriscado
    ltv = inputs.get('valor_credito', 1) / inputs.get('valor_avaliacao', 1)
    if ltv < 0.5:
        score += 2.0
    elif ltv < 0.6:
        score += 1.5
    elif ltv < 0.7:
        score += 1.0
    else:
        score += 0.5

    # Tipologia e Liquidez
    tipologia_scores = {'Residencial (Alto Padrão)': 1.0, 'Residencial (Médio Padrão)': 1.5, 'Galpão Logístico (AAA)': 1.5, 'Laje Corporativa (AAA)': 1.0, 'Terreno (Urbano)': 0.5, 'Outros': 0.2}
    score += tipologia_scores.get(inputs.get('tipologia'), 0)

    # Estágio da Obra
    estagio_scores = {'Pronto': 1.0, 'Em Construção (Avançado)': 0.5, 'Projeto': 0.1}
    score += estagio_scores.get(inputs.get('estagio_obra'), 0)

    # Documentação
    doc_scores = {'Regular, sem ônus': 0.5, 'Regular, com ônus saneável': 0.2, 'Irregular ou com ônus impeditivo': -1.0}
    score += doc_scores.get(inputs.get('documentacao'), -1.0)
    
    return min(max(score, 1), 5) # Normaliza o score entre 1 e 5

def calcular_score_pilar2(inputs):
    """Calcula o score para o Pilar II: Análise do Crédito e do Devedor."""
    score = 0
    
    # Comprometimento de Renda / DSCR
    # DTI (Debt-to-Income) < 30% é ideal
    dti = inputs.get('parcela', 0) / inputs.get('renda_devedor', 1)
    if dti <= 0.3:
        score += 2.0
    elif dti <= 0.4:
        score += 1.0
    else:
        score += 0.2
        
    # Score de Crédito do Devedor
    score_credito = inputs.get('score_devedor', 0)
    if score_credito > 700:
        score += 1.5
    elif score_credito > 500:
        score += 1.0
    else:
        score += 0.5
        
    # Sistema de Amortização
    if inputs.get('amortizacao') == 'SAC':
        score += 1.0
    else:
        score += 0.5
        
    # Histórico de Pagamento
    hist_scores = {'Excelente (sem atrasos)': 0.5, 'Bom (atrasos pontuais)': 0.2, 'Ruim (inadimplente)': -2.0, 'Novo (sem histórico)': 0.1}
    score += hist_scores.get(inputs.get('historico_pgto'), 0)

    return min(max(score, 1), 5) # Normaliza o score entre 1 e 5

def calcular_score_pilar3_4(inputs):
    """Calcula o score para os Pilares III e IV: Estrutura e Cenário."""
    score = 0
    
    # Estrutura (Pilar III)
    if inputs.get('regime_fiduciario'):
        score += 1.5
    
    # Garantias adicionais contam pontos
    score += len(inputs.get('garantias_adic', [])) * 0.5

    # Qualidade da Securitizadora
    qualidade_sec_scores = {'Tier 1 (Excelente Reputação)': 1.0, 'Tier 2 (Boa Reputação)': 0.6, 'Tier 3 (Pouca Experiência)': 0.2}
    score += qualidade_sec_scores.get(inputs.get('qualidade_sec'), 0)

    # Cenário (Pilar IV)
    cenario_juros_scores = {'Baixista': 0.5, 'Estável': 0.3, 'Altista': 0.1}
    score += cenario_juros_scores.get(inputs.get('cenario_juros'), 0)
    
    momento_setor_scores = {'Expansão': 0.5, 'Estável': 0.3, 'Contração': 0.1}
    score += momento_setor_scores.get(inputs.get('momento_setor'), 0)

    return min(max(score, 1), 5) # Normaliza o score entre 1 e 5

def map_score_to_rating(score):
    """Mapeia o score final para a classificação de rating."""
    if score >= 4.7:
        return 'AAA'
    elif score >= 4.3:
        return 'AA+'
    elif score >= 4.0:
        return 'AA'
    elif score >= 3.7:
        return 'A+'
    elif score >= 3.4:
        return 'A'
    elif score >= 3.0:
        return 'B+'
    elif score >= 2.5:
        return 'B'
    elif score >= 2.0:
        return 'C'
    else:
        return 'D'

# --- Definição das Abas ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📝 Informações Gerais",
    "🏠 Pilar I: Lastro Imobiliário", 
    "👤 Pilar II: Crédito e Devedor",
    "🏛️ Pilares III & IV: Estrutura e Cenário",
    "📊 Resultado do Rating",
    "📖 Metodologia"
])

# --- Aba 1: Informações Gerais ---
with tab1:
    st.header("Informações Gerais da Operação")
    st.session_state.inputs['info_gerais']['nome_operacao'] = st.text_input("Nome da Operação/CCI", "CCI Exemplo Residencial")
    st.session_state.inputs['info_gerais']['analista'] = st.text_input("Analista Responsável", "Seu Nome")
    st.session_state.inputs['pilar2']['valor_credito'] = st.number_input("Valor do Crédito (R$)", min_value=0.0, value=500000.0, step=50000.0, key='valor_credito_gerais')
    st.session_state.inputs['pilar1']['valor_avaliacao'] = st.number_input("Valor de Avaliação do Imóvel (R$)", min_value=0.0, value=1000000.0, step=50000.0, key='valor_avaliacao_gerais')
    
    if st.session_state.inputs['pilar1']['valor_avaliacao'] > 0:
        ltv_calculado = (st.session_state.inputs['pilar2']['valor_credito'] / st.session_state.inputs['pilar1']['valor_avaliacao']) * 100
        st.metric("Loan-to-Value (LTV) da Operação", f"{ltv_calculado:.2f}%")
    else:
        st.warning("Insira o valor de avaliação do imóvel para calcular o LTV.")

# --- Aba 2: Pilar I (Lastro Imobiliário) ---
with tab2:
    st.header("Pilar I: Análise do Lastro Imobiliário (Peso: 40%)")
    p1 = st.session_state.inputs['pilar1']
    
    col1, col2 = st.columns(2)
    with col1:
        p1['data_avaliacao'] = st.date_input("Data da Avaliação do Imóvel", datetime.date.today())
        p1['tipologia'] = st.selectbox("Tipologia do Imóvel", ['Residencial (Médio Padrão)', 'Residencial (Alto Padrão)', 'Galpão Logístico (AAA)', 'Laje Corporativa (AAA)', 'Terreno (Urbano)', 'Outros'])
        p1['liquidez_regiao'] = st.slider("Nota de Liquidez da Região", 1, 5, 3)

    with col2:
        p1['estagio_obra'] = st.radio("Estágio da Obra", ['Pronto', 'Em Construção (Avançado)', 'Projeto'])
        p1['documentacao'] = st.selectbox("Situação da Matrícula do Imóvel", ['Regular, sem ônus', 'Regular, com ônus saneável', 'Irregular ou com ônus impeditivo'])

# --- Aba 3: Pilar II (Crédito e Devedor) ---
with tab3:
    st.header("Pilar II: Análise do Crédito e do Devedor (Peso: 35%)")
    p2 = st.session_state.inputs['pilar2']

    col1, col2 = st.columns(2)
    with col1:
        p2['renda_devedor'] = st.number_input("Renda Mensal / Geração de Caixa do Devedor (R$)", min_value=0.0, value=15000.0, step=1000.0)
        p2['parcela'] = st.number_input("Valor da Parcela Mensal (R$)", min_value=0.0, value=4000.0, step=100.0)
        if p2['renda_devedor'] > 0:
            dti_calculado = (p2['parcela'] / p2['renda_devedor']) * 100
            st.metric("Comprometimento de Renda / DTI", f"{dti_calculado:.2f}%")
        p2['amortizacao'] = st.selectbox("Sistema de Amortização", ["SAC", "Price"])

    with col2:
        p2['score_devedor'] = st.slider("Score de Crédito do Devedor (Ex: Serasa)", 0, 1000, 750)
        p2['perfil_devedor'] = st.selectbox("Perfil do Devedor", ["Pessoa Física", "Pessoa Jurídica"])
        p2['historico_pgto'] = st.selectbox("Histórico de Pagamento", ['Novo (sem histórico)', 'Excelente (sem atrasos)', 'Bom (atrasos pontuais)', 'Ruim (inadimplente)'])

# --- Aba 4: Pilares III & IV (Estrutura e Cenário) ---
with tab4:
    st.header("Pilar III: Análise da Estrutura da Operação (Peso: 15%)")
    p3_4 = st.session_state.inputs['pilar3_4']

    col1, col2 = st.columns(2)
    with col1:
        p3_4['qualidade_sec'] = st.selectbox("Qualidade do Emissor/Securitizadora", ['Tier 1 (Excelente Reputação)', 'Tier 2 (Boa Reputação)', 'Tier 3 (Pouca Experiência)'])
        p3_4['regime_fiduciario'] = st.checkbox("Operação possui Regime Fiduciário?", value=True)
    
    with col2:
        p3_4['garantias_adic'] = st.multiselect("Garantias Adicionais", ["Fiança dos Sócios", "Fundo de Reserva", "Seguro Adicional", "Cessão de Recebíveis"])
    
    st.divider()
    
    st.header("Pilar IV: Análise de Cenário Macroeconômico e Setorial (Peso: 10%)")
    col3, col4 = st.columns(2)
    with col3:
        p3_4['cenario_juros'] = st.select_slider("Visão para Taxa de Juros (Selic)", ["Baixista", "Estável", "Altista"])
    with col4:
        p3_4['momento_setor'] = st.select_slider("Momento do Setor Imobiliário Específico", ["Expansão", "Estável", "Contração"])

# --- Aba 5: Resultado do Rating ---
with tab5:
    st.header("Resultado da Análise de Rating")

    if st.button("Calcular Rating da CCI"):
        # Armazena todos os inputs em um único dicionário para os cálculos
        all_inputs = {
            **st.session_state.inputs['info_gerais'],
            **st.session_state.inputs['pilar1'],
            **st.session_state.inputs['pilar2'],
            **st.session_state.inputs['pilar3_4'],
        }

        # Calcular scores
        score_p1 = calcular_score_pilar1(all_inputs)
        score_p2 = calcular_score_pilar2(all_inputs)
        score_p3_4 = calcular_score_pilar3_4(all_inputs)
        
        # Pesos
        weights = {'p1': 0.40, 'p2': 0.35, 'p3_4': 0.25} # p3 e p4 somam 25%
        
        # Score Final Ponderado
        final_score = (score_p1 * weights['p1']) + \
                      (score_p2 * weights['p2']) + \
                      (score_p3_4 * weights['p3_4'])
        
        # Rating Final
        final_rating = map_score_to_rating(final_score)
        
        # Salvar resultados no session_state
        st.session_state.inputs['resultado'] = {
            'score_p1': score_p1,
            'score_p2': score_p2,
            'score_p3_4': score_p3_4,
            'score_final': final_score,
            'rating_final': final_rating,
            'data_analise': datetime.datetime.now()
        }
        
    # Exibição dos resultados (só aparece depois de calcular)
    if 'rating_final' in st.session_state.inputs['resultado']:
        res = st.session_state.inputs['resultado']
        
        st.subheader(f"Rating Final Atribuído: {res['rating_final']}")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.metric("Score Final Ponderado", f"{res['score_final']:.2f} / 5.0")
            st.progress(res['score_final'] / 5)
        
        st.divider()
        st.subheader("Detalhamento por Pilar:")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Score Pilar I (Lastro)", f"{res['score_p1']:.2f}")
        c2.metric("Score Pilar II (Crédito)", f"{res['score_p2']:.2f}")
        c3.metric("Score Pilares III & IV (Estrutura/Cenário)", f"{res['score_p3_4']:.2f}")
        
        st.info(f"Análise realizada por **{st.session_state.inputs['info_gerais']['analista']}** em {res['data_analise'].strftime('%d/%m/%Y %H:%M:%S')}")

        # --- Geração do Relatório e Salvamento ---
        st.divider()
        st.subheader("Salvar e Gerar Relatório")
        
        if st.button("Salvar Análise e Gerar Relatório"):
            # Preparar dados para salvar
            report_data = {
                'Data_Analise': [res['data_analise']],
                'Operacao_CCI': [st.session_state.inputs['info_gerais']['nome_operacao']],
                'Analista': [st.session_state.inputs['info_gerais']['analista']],
                'Rating_Final': [res['rating_final']],
                'Score_Final': [f"{res['score_final']:.2f}"],
                **{f"input_{k}": [v] for k, v in st.session_state.inputs['pilar1'].items()},
                **{f"input_{k}": [v] for k, v in st.session_state.inputs['pilar2'].items()},
                **{f"input_{k}": [v] for k, v in st.session_state.inputs['pilar3_4'].items()},
            }
            df_report = pd.DataFrame(report_data)
            
            # Lógica para salvar em CSV
            filename = "historico_analises_cci.csv"
            if os.path.exists(filename):
                df_historico = pd.read_csv(filename)
                df_final = pd.concat([df_historico, df_report], ignore_index=True)
            else:
                df_final = df_report
            
            df_final.to_csv(filename, index=False)
            st.success(f"Análise salva com sucesso no arquivo '{filename}'!")

            # Exibição do relatório na tela
            with st.expander("Visualizar Relatório Completo da Análise"):
                for key, value in st.session_state.inputs.items():
                    if key != 'resultado':
                        st.write(f"**Seção: {key.replace('_', ' ').title()}**")
                        st.json(value)
                st.write("**Resultado:**")
                st.json({k: str(v) for k, v in res.items()})

# --- Aba 6: Metodologia ---
with tab6:
    st.header("Metodologia de Rating para CCIs")
    st.markdown("""
    O rating de CCI é determinado por uma análise ponderada de quatro pilares fundamentais, visando capturar todas as fontes de risco da operação.
    
    ### Pilar I: Análise do Lastro Imobiliário (Peso: 40%)
    Foca na qualidade e liquidez da garantia real.
    - **Inputs:** Laudo de Avaliação, Localização e Mercado, Características Físicas e Documentais do Imóvel.
    - **Métricas Chave:** Loan-to-Value (LTV), liquidez da região, regularidade da matrícula.

    ### Pilar II: Análise do Crédito e do Devedor (Peso: 35%)
    Avalia a capacidade e disposição do devedor em honrar com os pagamentos.
    - **Inputs:** Perfil do Devedor (PF ou PJ), Métricas do Crédito, Histórico de Pagamento.
    - **Métricas Chave:** Comprometimento de Renda (DTI), Índice de Cobertura do Serviço da Dívida (DSCR), Score de Crédito.

    ### Pilar III: Análise da Estrutura da Operação (Peso: 15%)
    Analisa os mecanismos legais e financeiros que protegem o investidor.
    - **Inputs:** Qualidade do Emissor/Securitizadora, Estrutura de Garantias, Covenants.
    - **Métricas Chave:** Existência de Regime Fiduciário, garantias adicionais, fundo de reserva.

    ### Pilar IV: Análise de Cenário Macroeconômico e Setorial (Peso: 10%)
    Contextualiza a operação dentro do ambiente de mercado e riscos sistêmicos.
    - **Inputs:** Cenário Macroeconômico (Juros, Inflação, PIB), Cenário Setorial Imobiliário.
    - **Métricas Chave:** Tendência da Taxa Selic, ciclo de mercado do setor imobiliário específico.
    
    O score final é uma média ponderada dos scores atribuídos a cada pilar, que é então mapeado para uma escala de rating de 'AAA' a 'D'.
    """)
