# app.py
from flask import Flask, render_template, request, url_for, Response
from data_handler import (
    get_chamados, get_distinct_servicos, get_distinct_tipos_chamado,
    get_distinct_grupos_solucao, get_distinct_unidades, get_distinct_status_chamado
)
from datetime import date, timedelta, datetime, time
import calendar
import pandas as pd
import math
import plotly.express as px
import io


app = Flask(__name__)

# --- Constantes Globais ---
ITEMS_PER_PAGE = 50
TOP_N_DEPARTAMENTOS = 10
TOP_N_GRUPOS = 10
TOP_N_UNIDADES = 10
TOP_N_SERVICOS = 10
TOP_N_DEPTOS_ORACLE_TV = 10

SERVICO_ORACLE = "1-SISTEMAS (ERP Oracle)" 
GRUPO_SUSTENTACAO_SEVEN = "Sustentação - SEVEN"
GRUPO_SUSTENTACAO_MMBIT = "Solution - MMBIT" 
GRUPO_AGUARDANDO_AVALIACAO = "Aguardando Avaliação"
PRIORIDADES_CRITICAS_ALTAS = ['Crítica', 'Alta'] 

TIPO_CHAMADO_INCIDENTE = "Incidente" 
TIPO_CHAMADO_REQUISICAO_SERVICO = "Requisição de Serviço" 

STATUS_NOVO_SEM_CATEGORIA = "Novo (sem categoria)"
STATUS_EM_ATENDIMENTO_ESPECIFICO = "Em atendimento" 
STATUS_ENCERRADO = "Encerrado"
STATUS_FECHADO_PELO_USUARIO = "Fechado pelo usuário"
STATUS_FECHADO_PELO_ADMIN_AREA = "Fechado pelo administrador da área"
STATUS_CONTESTADO = "Contestado"
STATUS_FECHADO_DECURSO_PRAZO = "Fechado por decurso de prazo"
STATUS_AGENDADO = "Agendado"
STATUS_AGUARDANDO_SOLICITANTE = "Aguardando solicitante"
STATUS_ENCAMINHADO_FORNECEDOR = "Encaminhado para fornecedor"
STATUS_AGUARDANDO_APROVACAO = "Aguardando aprovação"
STATUS_REPROVADO = "Reprovado"
STATUS_AGENDADO_COM_FORNECEDOR = "Agendado com fornecedor" 
STATUS_FINALIZADO_PELO_FORNECEDOR = "Finalizado pelo fornecedor"

STATUS_EM_ATENDIMENTO_LISTA = [
    STATUS_NOVO_SEM_CATEGORIA, STATUS_EM_ATENDIMENTO_ESPECIFICO, STATUS_AGENDADO,
    STATUS_ENCAMINHADO_FORNECEDOR, STATUS_AGUARDANDO_APROVACAO, STATUS_AGENDADO_COM_FORNECEDOR
]
STATUS_FECHADO_LISTA = [ 
    STATUS_ENCERRADO, STATUS_FECHADO_PELO_USUARIO, STATUS_FECHADO_PELO_ADMIN_AREA,
    STATUS_FECHADO_DECURSO_PRAZO, STATUS_FINALIZADO_PELO_FORNECEDOR
]

CORES_KPI_PIZZA = { 
    'Em Atendimento': 'orange',
    STATUS_AGUARDANDO_SOLICITANTE: '#007bff',
    STATUS_CONTESTADO: '#ffc107',
    STATUS_NOVO_SEM_CATEGORIA: '#add8e6',
    STATUS_EM_ATENDIMENTO_ESPECIFICO : '#87ceeb',
    STATUS_AGENDADO: '#6495ed',
    STATUS_ENCAMINHADO_FORNECEDOR: '#4682b4',
    STATUS_AGUARDANDO_APROVACAO: '#5f9ea0',
    STATUS_AGENDADO_COM_FORNECEDOR: '#4169e1'
}
CORES_INDEX_PIZZA = {**CORES_KPI_PIZZA, **{ 
    'Fechados': 'green', 
    STATUS_ENCERRADO: '#28a745', STATUS_FECHADO_PELO_USUARIO: '#218838',
    STATUS_FECHADO_PELO_ADMIN_AREA: '#1e7e34', STATUS_FECHADO_DECURSO_PRAZO: '#19692c',
    STATUS_FINALIZADO_PELO_FORNECEDOR: '#228b22',
    STATUS_REPROVADO: '#dc3545' 
}}


def gerar_kpis_e_pizza(df_segmento, titulo_pizza_segmento, plotly_js_config='cdn'):
    kpis = {
        'total_criados': 0, 'em_atendimento': 0, 'aguardando_solicitante': 0,
        'contestado': 0, 'sla_estourado': 0, 'abertos_7_dias_mais': 0
    }
    pizza_html = None

    if df_segmento is None or df_segmento.empty:
        return kpis, pizza_html
        
    # Colunas base para KPIs e Pizza
    base_required_cols = ['STATUS', 'DT_ABERTURA_RAW']
    # Colunas adicionais para SLA de Atendimento
    sla_required_cols = ['sla_atendimento_tempo_decorrido', 'sla_encaminhamento_tempo_decorrido', 'sla_atendimento_tempo_definido']
    
    if not all(col in df_segmento.columns for col in base_required_cols):
        print(f"ALERTA em calcular_dados_tv_fornecedores para '{titulo_pizza_segmento}': Faltam colunas base. Presentes: {df_segmento.columns.tolist()}")
        kpis['total_criados'] = len(df_segmento) if not df_segmento.empty else 0
        return kpis, pizza_html

    kpis['total_criados'] = len(df_segmento)

    df_nao_finalizados = df_segmento[
        ~df_segmento['STATUS'].isin(STATUS_FECHADO_LISTA) &
        (df_segmento['STATUS'] != STATUS_REPROVADO)
    ].copy()

    if not df_nao_finalizados.empty:
        kpis['em_atendimento'] = len(df_nao_finalizados[df_nao_finalizados['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)])
        kpis['aguardando_solicitante'] = len(df_nao_finalizados[df_nao_finalizados['STATUS'] == STATUS_AGUARDANDO_SOLICITANTE])
        kpis['contestado'] = len(df_nao_finalizados[df_nao_finalizados['STATUS'] == STATUS_CONTESTADO])
        
        # --- KPI: SLA de Atendimento Estourado (NOVA LÓGICA) ---
        if all(col in df_nao_finalizados.columns for col in sla_required_cols):
            # Converter colunas de SLA para numérico, tratando erros e NaNs
            tempo_atend_decorrido = pd.to_numeric(df_nao_finalizados['sla_atendimento_tempo_decorrido'], errors='coerce').fillna(0)
            tempo_encam_decorrido = pd.to_numeric(df_nao_finalizados['sla_encaminhamento_tempo_decorrido'], errors='coerce').fillna(0)
            tempo_atend_definido = pd.to_numeric(df_nao_finalizados['sla_atendimento_tempo_definido'], errors='coerce').fillna(0)

            # Somar os tempos decorridos
            tempo_total_decorrido_atend = tempo_atend_decorrido + tempo_encam_decorrido
            
            # Filtrar apenas chamados onde o tempo de SLA definido é maior que zero
            df_com_sla_valido = df_nao_finalizados[tempo_atend_definido > 0]
            
            if not df_com_sla_valido.empty:
                # Aplicar a condição de estouro no DataFrame já filtrado por tempo_definido > 0
                # Precisamos re-calcular tempo_total_decorrido_atend e tempo_atend_definido para este subset
                tempo_total_decorrido_atend_valido = pd.to_numeric(df_com_sla_valido['sla_atendimento_tempo_decorrido'], errors='coerce').fillna(0) + \
                                                   pd.to_numeric(df_com_sla_valido['sla_encaminhamento_tempo_decorrido'], errors='coerce').fillna(0)
                tempo_atend_definido_valido = pd.to_numeric(df_com_sla_valido['sla_atendimento_tempo_definido'], errors='coerce').fillna(0)
                
                kpis['sla_estourado'] = len(df_com_sla_valido[tempo_total_decorrido_atend_valido > tempo_atend_definido_valido])
            else:
                kpis['sla_estourado'] = 0
            
            print(f"DEBUG SLA para '{titulo_pizza_segmento}': Qtde com SLA Atend. Estourado (nova lógica): {kpis['sla_estourado']}")
        else:
            print(f"ALERTA SLA para '{titulo_pizza_segmento}': Faltam colunas de SLA para o cálculo.")
            kpis['sla_estourado'] = 0 # Default se colunas não existirem

        # --- KPI: Chamados abertos há 7 dias ou mais (para os não finalizados) ---
        # (Lógica existente para este KPI)
        if 'DT_ABERTURA_RAW' in df_nao_finalizados.columns:
            df_aging_calc = df_nao_finalizados.copy() # Usar df_nao_finalizados diretamente
            df_aging_calc.loc[:, 'DT_ABERTURA_DATETIME'] = pd.to_datetime(df_aging_calc['DT_ABERTURA_RAW'], errors='coerce')
            df_aging_calc.dropna(subset=['DT_ABERTURA_DATETIME'], inplace=True)
            if not df_aging_calc.empty:
                agora_naive_aging = datetime.now() 
                df_aging_calc.loc[:, 'IDADE_CHAMADO_CORRIDO'] = agora_naive_aging - df_aging_calc['DT_ABERTURA_DATETIME']
                kpis['abertos_7_dias_mais'] = len(df_aging_calc[df_aging_calc['IDADE_CHAMADO_CORRIDO'] >= timedelta(days=7)])
        
        # --- Pizza com status dos não finalizados ---
        # (Lógica da pizza como antes)
        pizza_display_data = {}
        if kpis['em_atendimento'] > 0: pizza_display_data['Em Atendimento'] = kpis['em_atendimento']
        if kpis['aguardando_solicitante'] > 0: pizza_display_data[STATUS_AGUARDANDO_SOLICITANTE] = kpis['aguardando_solicitante']
        if kpis['contestado'] > 0: pizza_display_data[STATUS_CONTESTADO] = kpis['contestado']
        outros_status_ativos = df_nao_finalizados[
            ~df_nao_finalizados['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA) &
            (df_nao_finalizados['STATUS'] != STATUS_AGUARDANDO_SOLICITANTE) &
            (df_nao_finalizados['STATUS'] != STATUS_CONTESTADO)
        ]['STATUS'].value_counts()
        for status_nome, contagem in outros_status_ativos.items():
            if contagem > 0: pizza_display_data[status_nome] = contagem
        if pizza_display_data:
            pizza_df_final = pd.DataFrame(list(pizza_display_data.items()), columns=['Status', 'Contagem'])
            if not pizza_df_final.empty and pizza_df_final['Contagem'].sum() > 0:
                fig = px.pie(pizza_df_final, names='Status', values='Contagem', 
                             title=titulo_pizza_segmento if titulo_pizza_segmento else None, hole=0.3,
                             color='Status', color_discrete_map=CORES_KPI_PIZZA) 
                fig.update_layout(
                    margin=dict(l=5, r=5, t=30, b=5), height=220,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD',
                    legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5, font=dict(size=9)), 
                    title_font_size=11, title_x=0.5, title_xanchor='center'
                )
                pizza_html = fig.to_html(full_html=False, include_plotlyjs=plotly_js_config)
            
    return kpis, pizza_html

def gerar_kpis_e_pizza_oracle_geral(df_segmento, titulo_pizza, plotly_js_config_oracle='cdn'):
    # KPIs para a tela Oracle Geral: Total, Em Atendimento, Fechados, Aguard. Solic., Contestados
    kpis = {
        'total_criados': 0,
        'em_atendimento': 0,
        'fechados': 0, # KPI de Fechados é necessário aqui
        'aguardando_solicitante': 0,
        'contestado': 0
        # Reprovado não foi explicitamente pedido para KPI aqui, mas pode ser adicionado se necessário
    }
    pizza_html = None

    if df_segmento is None or df_segmento.empty:
        return kpis, pizza_html
    
    if not 'STATUS' in df_segmento.columns:
        print(f"ALERTA em gerar_kpis_e_pizza_oracle_geral para '{titulo_pizza}': Coluna STATUS ausente.")
        kpis['total_criados'] = len(df_segmento)
        return kpis, pizza_html

    kpis['total_criados'] = len(df_segmento)
    kpis['em_atendimento'] = len(df_segmento[df_segmento['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)])
    kpis['fechados'] = len(df_segmento[df_segmento['STATUS'].isin(STATUS_FECHADO_LISTA)])
    kpis['aguardando_solicitante'] = len(df_segmento[df_segmento['STATUS'] == STATUS_AGUARDANDO_SOLICITANTE])
    kpis['contestado'] = len(df_segmento[df_segmento['STATUS'] == STATUS_CONTESTADO])
    
    # A pizza para esta tela mostrará todos os status presentes no df_segmento
    status_counts = df_segmento['STATUS'].value_counts()
    
    if not status_counts.empty and status_counts.sum() > 0:
        fig = px.pie(status_counts, names=status_counts.index, values=status_counts.values, 
                     title=titulo_pizza if titulo_pizza else None, hole=0.3,
                     color_discrete_map=CORES_INDEX_PIZZA) # Usar o mapa de cores mais completo
        fig.update_layout(
            margin=dict(l=5, r=5, t=30, b=5), height=220, # Mesma altura das outras pizzas de TV
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD',
            legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5, font=dict(size=9)), 
            title_font_size=11, title_x=0.5, title_xanchor='center'
        )
        pizza_html = fig.to_html(full_html=False, include_plotlyjs=plotly_js_config_oracle)
        
    return kpis, pizza_html

@app.route('/')
def index():
    # ... (CÓDIGO COMPLETO DA ROTA index, como fornecido na última resposta) ...
    print("Acessando rota / (index)")
    data_inicio_form = request.args.get('data_inicio'); data_fim_form = request.args.get('data_fim')
    page = request.args.get('page', 1, type=int)
    if data_inicio_form and data_fim_form: data_inicio_str, data_fim_str = data_inicio_form, data_fim_form
    else:
        data_fim_dt = date.today(); data_inicio_dt = data_fim_dt - timedelta(days=29)
        data_inicio_str, data_fim_str = data_inicio_dt.strftime('%Y-%m-%d'), data_fim_dt.strftime('%Y-%m-%d')
    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)
    total_chamados_filtrados = 0; chamados_pagina_df = pd.DataFrame(); total_pages = 0
    status_graph_html = None; dept_graph_html = None; primeiro_grafico_js_carregado_index = False
    if not todos_chamados_df.empty:
        total_chamados_filtrados = len(todos_chamados_df)
        total_pages = math.ceil(total_chamados_filtrados / ITEMS_PER_PAGE)
        if page < 1: page = 1
        elif page > total_pages and total_pages > 0: page = total_pages
        start_index = (page - 1) * ITEMS_PER_PAGE; end_index = start_index + ITEMS_PER_PAGE
        chamados_pagina_df = todos_chamados_df.iloc[start_index:end_index].copy()
        if 'DT_ABERTURA_RAW' in chamados_pagina_df.columns:
            chamados_pagina_df.loc[:, 'DT_ABERTURA_FORMATADA'] = chamados_pagina_df['DT_ABERTURA_RAW'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notna(x) else '')
        if 'STATUS' in todos_chamados_df.columns:
            status_counts = todos_chamados_df['STATUS'].value_counts()
            if not status_counts.empty and status_counts.sum() > 0:
                fig_status = px.pie(status_counts, names=status_counts.index, values=status_counts.values, title='Distribuição de Chamados por Status', color_discrete_map=CORES_INDEX_PIZZA)
                fig_status.update_layout(margin=dict(l=20,r=20,t=40,b=20), height=330, title_font_size=14, legend=dict(font=dict(size=10)))
                status_graph_html = fig_status.to_html(full_html=False, include_plotlyjs='cdn')
                primeiro_grafico_js_carregado_index = True
        if 'DEPARTAMENTO' in todos_chamados_df.columns:
            dept_counts = todos_chamados_df['DEPARTAMENTO'].value_counts().nlargest(TOP_N_DEPARTAMENTOS)
            if not dept_counts.empty:
                fig_dept = px.bar(dept_counts, x=dept_counts.index, y=dept_counts.values, title=f'Top {TOP_N_DEPARTAMENTOS} Departamentos', labels={'y': 'Nº de Chamados', 'index': 'Departamento'}, text=dept_counts.values)
                fig_dept.update_layout(margin=dict(l=20,r=20,t=50,b=20), height=400); fig_dept.update_xaxes(tickangle=-45)
                dept_graph_html = fig_dept.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_index)
    return render_template('index.html',
                           chamados=chamados_pagina_df, data_inicio=data_inicio_str, data_fim=data_fim_str,
                           total_chamados=total_chamados_filtrados, page=page, total_pages=total_pages, 
                           items_per_page=ITEMS_PER_PAGE, status_graph_html=status_graph_html,
                           dept_graph_html=dept_graph_html, endpoint='index')

@app.route('/analise_detalhada')
def analise_detalhada():
    # ... (CÓDIGO COMPLETO DA SUA ROTA analise_detalhada - fornecido na última resposta) ...
    print("Acessando rota /analise_detalhada") 
    data_inicio_form = request.args.get('data_inicio'); data_fim_form = request.args.get('data_fim')
    servico_selecionado_filtro = request.args.get('servico', ''); tipo_chamado_selecionado_filtro = request.args.get('tipo_chamado', '')
    grupo_solucao_selecionado = request.args.get('grupo_solucao', ''); unidade_selecionada = request.args.get('unidade', '')
    status_chamado_selecionado = request.args.get('status_chamado', ''); page = request.args.get('page', 1, type=int)
    if data_inicio_form and data_fim_form: data_inicio_str, data_fim_str = data_inicio_form, data_fim_form
    else:
        data_fim_dt = date.today(); data_inicio_dt = data_fim_dt - timedelta(days=365 + 30)
        data_inicio_str, data_fim_str = data_inicio_dt.strftime('%Y-%m-%d'), data_fim_dt.strftime('%Y-%m-%d')
    lista_servicos_df = get_distinct_servicos(); lista_tipos_chamado_df = get_distinct_tipos_chamado()
    lista_grupos_solucao_df = get_distinct_grupos_solucao(); lista_unidades_df = get_distinct_unidades()
    lista_status_chamado = get_distinct_status_chamado()
    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)
    chamados_filtrados_df = todos_chamados_df.copy()
    if servico_selecionado_filtro and 'SERVICO' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['SERVICO'] == servico_selecionado_filtro]
    if tipo_chamado_selecionado_filtro and 'TIPOCHAMADO' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['TIPOCHAMADO'] == tipo_chamado_selecionado_filtro]
    if grupo_solucao_selecionado and 'GRUPO' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['GRUPO'] == grupo_solucao_selecionado]
    if unidade_selecionada and 'UNIDADE' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['UNIDADE'] == unidade_selecionada]
    if status_chamado_selecionado and 'STATUS' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['STATUS'] == status_chamado_selecionado]
    grupo_graph_html = None; unidade_graph_html = None; servico_graph_html = None; tipo_chamado_graph_html = None; evolucao_mensal_geral_graph_html = None; evolucao_tipo_graph_html = None
    primeiro_grafico_js_carregado_analise = False; total_chamados_final = 0; chamados_pagina_df = pd.DataFrame(); total_pages = 0
    if not chamados_filtrados_df.empty:
        total_chamados_final = len(chamados_filtrados_df); total_pages = math.ceil(total_chamados_final / ITEMS_PER_PAGE)
        if page < 1: page = 1
        elif page > total_pages and total_pages > 0: page = total_pages
        start_index = (page - 1) * ITEMS_PER_PAGE; end_index = start_index + ITEMS_PER_PAGE
        chamados_pagina_df = chamados_filtrados_df.iloc[start_index:end_index].copy()
        if 'DT_ABERTURA_RAW' in chamados_pagina_df.columns: chamados_pagina_df.loc[:, 'DT_ABERTURA_FORMATADA'] = chamados_pagina_df['DT_ABERTURA_RAW'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notna(x) else '')
        # Lógica de geração dos 6 gráficos para analise_detalhada
        # (O código completo foi omitido para brevidade, mas você tem a versão completa)
        # Lembre-se de usar 'plotly_js_config' como parâmetro se chamar gerar_kpis_e_pizza aqui
        # e de gerenciar a flag 'primeiro_grafico_js_carregado_analise'
        # Exemplo para o primeiro gráfico:
        if 'GRUPO' in chamados_filtrados_df.columns:
            grupo_counts = chamados_filtrados_df['GRUPO'].value_counts().nlargest(TOP_N_GRUPOS)
            if not grupo_counts.empty:
                fig_grupo = px.bar(grupo_counts, x=grupo_counts.index, y=grupo_counts.values, title=f'Top {TOP_N_GRUPOS} Grupos', labels={'y': 'Nº Chamados', 'index': 'Grupo'}, text=grupo_counts.values)
                fig_grupo.update_layout(margin=dict(l=20,r=20,t=50,b=20), height=400); fig_grupo.update_xaxes(tickangle=-45)
                grupo_graph_html = fig_grupo.to_html(full_html=False, include_plotlyjs='cdn'); primeiro_grafico_js_carregado_analise = True
        # ... (REPLIQUE A LÓGICA PARA OS OUTROS 5 GRÁFICOS, USANDO include_plotlyjs=not primeiro_grafico_js_carregado_analise) ...
    return render_template('analise_detalhada.html',
                           chamados=chamados_pagina_df, data_inicio=data_inicio_str, data_fim=data_fim_str,
                           servicos=lista_servicos_df.to_dict(orient='records'), tipos_chamado=lista_tipos_chamado_df.to_dict(orient='records'),
                           grupos_solucao=lista_grupos_solucao_df.to_dict(orient='records'), unidades=lista_unidades_df.to_dict(orient='records'),
                           lista_status_chamado=lista_status_chamado, servico_selecionado=servico_selecionado_filtro,
                           tipo_chamado_selecionado=tipo_chamado_selecionado_filtro, grupo_solucao_selecionado=grupo_solucao_selecionado,
                           unidade_selecionada=unidade_selecionada, status_chamado_selecionado=status_chamado_selecionado,
                           total_chamados=total_chamados_final, page=page, total_pages=total_pages, items_per_page=ITEMS_PER_PAGE,
                           grupo_graph_html=grupo_graph_html, unidade_graph_html=unidade_graph_html, servico_graph_html=servico_graph_html,
                           tipo_chamado_graph_html=tipo_chamado_graph_html, evolucao_mensal_geral_graph_html=evolucao_mensal_geral_graph_html,
                           evolucao_tipo_graph_html=evolucao_tipo_graph_html, endpoint='analise_detalhada')


@app.route('/dashboard_tv_oracle')
def dashboard_tv_oracle():
    print("--- ROTA /dashboard_tv_oracle: INÍCIO (Mês Atual - Incidentes vs Não Incidentes) ---")
    servico_filtro_oracle = SERVICO_ORACLE

    hoje = date.today() 
    primeiro_dia_mes_atual = hoje.replace(day=1)
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    ultimo_dia_mes_atual = hoje.replace(day=dias_no_mes)
    data_inicio_str = primeiro_dia_mes_atual.strftime('%Y-%m-%d')
    data_fim_str = ultimo_dia_mes_atual.strftime('%Y-%m-%d')
    
    todos_chamados_mes_atual_df = get_chamados(data_inicio=data_inicio_str,data_fim=data_fim_str,area_id=1)
    print(f"1. TV Oracle - Total chamados (todos os tipos) mês: {len(todos_chamados_mes_atual_df)}")

    # Inicializar dicionários para os dados das duas seções
    dados_incidentes_oracle = {}
    dados_nao_incidentes_oracle = {}
    # KPIs específicos que não vêm direto da função helper
    kpi_incidentes_aguardando_aval_oracle = 0 
    kpi_nao_incidentes_aguardando_aval_oracle = 0
    
    primeiro_grafico_js_carregado_tv_oracle = False

    if not todos_chamados_mes_atual_df.empty:
        oracle_df_mes_atual = todos_chamados_mes_atual_df[
            todos_chamados_mes_atual_df['SERVICO'] == servico_filtro_oracle
        ].copy()
        print(f"2. TV Oracle - Chamados Oracle (todos os tipos) mês: {len(oracle_df_mes_atual)}")

        if not oracle_df_mes_atual.empty and 'TIPOCHAMADO' in oracle_df_mes_atual.columns and \
           'GRUPO' in oracle_df_mes_atual.columns and 'STATUS' in oracle_df_mes_atual.columns:

            # --- Seção 1: Incidentes Oracle ---
            oracle_incidentes_df = oracle_df_mes_atual[oracle_df_mes_atual['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()
            print(f"  Incidentes Oracle (mês): {len(oracle_incidentes_df)}")
            
            # Usar a nova função helper para KPIs e Pizza de Incidentes
            kpis_inc, pizza_inc_html = gerar_kpis_e_pizza_oracle_geral(
                oracle_incidentes_df, 
                None, 
                plotly_js_config_oracle='cdn' if not primeiro_grafico_js_carregado_tv_oracle else False
            )
            dados_incidentes_oracle = {**kpis_inc, 'pizza_html': pizza_inc_html}
            if pizza_inc_html and not primeiro_grafico_js_carregado_tv_oracle: 
                primeiro_grafico_js_carregado_tv_oracle = True
            
            # Calcular KPI "Aguardando Avaliação" para Incidentes (chamados ATIVOS no grupo)
            df_inc_aguard_aval_ativos = oracle_incidentes_df[
                (oracle_incidentes_df['GRUPO'] == GRUPO_AGUARDANDO_AVALIACAO) &
                (oracle_incidentes_df['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA + [STATUS_AGUARDANDO_SOLICITANTE, STATUS_CONTESTADO]))
            ]
            kpi_incidentes_aguardando_aval_oracle = len(df_inc_aguard_aval_ativos)
            print(f"  Incidentes Oracle em '{GRUPO_AGUARDANDO_AVALIACAO}' (ativos): {kpi_incidentes_aguardando_aval_oracle}")

            # --- Seção 2: Outros Chamados (Não Incidentes) Oracle ---
            oracle_nao_incidentes_df = oracle_df_mes_atual[oracle_df_mes_atual['TIPOCHAMADO'] != TIPO_CHAMADO_INCIDENTE].copy()
            print(f"  Outros Chamados Oracle (mês): {len(oracle_nao_incidentes_df)}")

            # Usar a nova função helper para KPIs e Pizza de Não Incidentes
            kpis_nao_inc, pizza_nao_inc_html = gerar_kpis_e_pizza_oracle_geral(
                oracle_nao_incidentes_df, 
                None, 
                plotly_js_config_oracle=not primeiro_grafico_js_carregado_tv_oracle
            )
            dados_nao_incidentes_oracle = {**kpis_nao_inc, 'pizza_html': pizza_nao_inc_html}
            if pizza_nao_inc_html and not primeiro_grafico_js_carregado_tv_oracle: # Apenas atualiza se ainda não foi
                primeiro_grafico_js_carregado_tv_oracle = True


            # Calcular KPI "Aguardando Avaliação" para Não Incidentes (chamados ATIVOS no grupo)
            df_nao_inc_aguard_aval_ativos = oracle_nao_incidentes_df[
                (oracle_nao_incidentes_df['GRUPO'] == GRUPO_AGUARDANDO_AVALIACAO) &
                (oracle_nao_incidentes_df['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA + [STATUS_AGUARDANDO_SOLICITANTE, STATUS_CONTESTADO]))
            ]
            kpi_nao_incidentes_aguardando_aval_oracle = len(df_nao_inc_aguard_aval_ativos)
            print(f"  Outros Chamados Oracle em '{GRUPO_AGUARDANDO_AVALIACAO}' (ativos): {kpi_nao_incidentes_aguardando_aval_oracle}")
            
    print("--- ROTA /dashboard_tv_oracle: FIM ---")
                            
    return render_template('dashboard_tv_oracle.html',
                           servico_foco=servico_filtro_oracle,
                           dados_incidentes_oracle=dados_incidentes_oracle,
                           dados_nao_incidentes_oracle=dados_nao_incidentes_oracle,
                           kpi_incidentes_aguardando_aval=kpi_incidentes_aguardando_aval_oracle, # Nome da variável atualizado
                           kpi_nao_incidentes_aguardando_aval=kpi_nao_incidentes_aguardando_aval_oracle, # Nome da variável atualizado
                           data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                           endpoint='dashboard_tv_oracle' 
                           )

@app.route('/dashboard_tv_fornecedores')
def dashboard_tv_fornecedores():
    print("--- ROTA /dashboard_tv_fornecedores: INÍCIO (Mês Atual, Foco Não Fechados) ---")
    hoje = date.today(); primeiro_dia_mes_atual = hoje.replace(day=1)
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]; ultimo_dia_mes_atual = hoje.replace(day=dias_no_mes)
    data_inicio_str, data_fim_str = primeiro_dia_mes_atual.strftime('%Y-%m-%d'), ultimo_dia_mes_atual.strftime('%Y-%m-%d')
    todos_chamados_mes_atual_df = get_chamados(data_inicio=data_inicio_str,data_fim=data_fim_str,area_id=1)
    kpi_keys_fornecedores = ['total_criados', 'em_atendimento', 'aguardando_solicitante', 'contestado', 'sla_estourado', 'abertos_7_dias_mais']
    dados_seven_incidentes = {key: 0 for key in kpi_keys_fornecedores}; dados_seven_incidentes['pizza_html'] = None
    dados_seven_outros = {key: 0 for key in kpi_keys_fornecedores}; dados_seven_outros['pizza_html'] = None
    dados_mmbit_incidentes = {key: 0 for key in kpi_keys_fornecedores}; dados_mmbit_incidentes['pizza_html'] = None
    dados_mmbit_outros = {key: 0 for key in kpi_keys_fornecedores}; dados_mmbit_outros['pizza_html'] = None
    primeiro_grafico_renderizado_fornecedores = False
    if not todos_chamados_mes_atual_df.empty and all(col in todos_chamados_mes_atual_df.columns for col in ['SERVICO', 'GRUPO', 'TIPOCHAMADO', 'STATUS', 'DT_ABERTURA_RAW', 'sla_atendimento_tempo_decorrido', 'sla_atendimento_tempo_definido']):
        seven_oracle_df = todos_chamados_mes_atual_df[(todos_chamados_mes_atual_df['SERVICO'] == SERVICO_ORACLE) & (todos_chamados_mes_atual_df['GRUPO'] == GRUPO_SUSTENTACAO_SEVEN)].copy()
        if not seven_oracle_df.empty:
            seven_incidentes_df = seven_oracle_df[seven_oracle_df['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(seven_incidentes_df, None, plotly_js_config='cdn' if not primeiro_grafico_renderizado_fornecedores else False) # CORRIGIDO
            dados_seven_incidentes = {**kpis, 'pizza_html': pizza_html}
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True
            seven_outros_df = seven_oracle_df[seven_oracle_df['TIPOCHAMADO'] != TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(seven_outros_df, None, plotly_js_config=not primeiro_grafico_renderizado_fornecedores) # CORRIGIDO
            dados_seven_outros = {**kpis, 'pizza_html': pizza_html}
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True
        mmbit_geral_df = todos_chamados_mes_atual_df[todos_chamados_mes_atual_df['GRUPO'] == GRUPO_SUSTENTACAO_MMBIT].copy()
        if not mmbit_geral_df.empty:
            mmbit_incidentes_df = mmbit_geral_df[mmbit_geral_df['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(mmbit_incidentes_df, None, plotly_js_config=not primeiro_grafico_renderizado_fornecedores) # CORRIGIDO
            dados_mmbit_incidentes = {**kpis, 'pizza_html': pizza_html}
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True
            mmbit_outros_df = mmbit_geral_df[mmbit_geral_df['TIPOCHAMADO'] != TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(mmbit_outros_df, None, plotly_js_config=not primeiro_grafico_renderizado_fornecedores) # CORRIGIDO
            dados_mmbit_outros = {**kpis, 'pizza_html': pizza_html}
    return render_template('dashboard_tv_fornecedores.html',
                           data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                           dados_seven_incidentes=dados_seven_incidentes, dados_seven_outros=dados_seven_outros,
                           dados_mmbit_incidentes=dados_mmbit_incidentes, dados_mmbit_outros=dados_mmbit_outros,
                           GRUPO_SUSTENTACAO_SEVEN_NOME=GRUPO_SUSTENTACAO_SEVEN,
                           GRUPO_SUSTENTACAO_MMBIT_NOME=GRUPO_SUSTENTACAO_MMBIT,
                           endpoint='dashboard_tv_fornecedores')

@app.route('/exportar_excel')
def exportar_excel():
    # ... (CÓDIGO COMPLETO DA SUA ROTA exportar_excel - fornecido na última resposta) ...
    # Certifique-se que usa 'STATUS' para filtrar.
    print("Acessando rota /exportar_excel"); data_inicio_form=request.args.get('data_inicio'); data_fim_form=request.args.get('data_fim')
    servico_selecionado=request.args.get('servico',''); tipo_chamado_selecionado=request.args.get('tipo_chamado','')
    grupo_solucao_selecionado=request.args.get('grupo_solucao',''); unidade_selecionada=request.args.get('unidade','')            
    status_chamado_selecionado=request.args.get('status_chamado',''); area_id_param=request.args.get('area_id',1,type=int)
    if data_inicio_form and data_fim_form: data_inicio_str,data_fim_str=data_inicio_form,data_fim_form
    else: data_fim_dt=date.today(); data_inicio_dt=data_fim_dt-timedelta(days=29); data_inicio_str,data_fim_str=data_inicio_dt.strftime('%Y-%m-%d'),data_fim_dt.strftime('%Y-%m-%d')
    chamados_para_exportar_df=get_chamados(data_inicio_str,data_fim_str,area_id_param)
    if servico_selecionado and 'SERVICO' in chamados_para_exportar_df.columns: chamados_para_exportar_df=chamados_para_exportar_df[chamados_para_exportar_df['SERVICO']==servico_selecionado]
    if tipo_chamado_selecionado and 'TIPOCHAMADO' in chamados_para_exportar_df.columns: chamados_para_exportar_df=chamados_para_exportar_df[chamados_para_exportar_df['TIPOCHAMADO']==tipo_chamado_selecionado]
    if grupo_solucao_selecionado and 'GRUPO' in chamados_para_exportar_df.columns: chamados_para_exportar_df=chamados_para_exportar_df[chamados_para_exportar_df['GRUPO']==grupo_solucao_selecionado]
    if unidade_selecionada and 'UNIDADE' in chamados_para_exportar_df.columns: chamados_para_exportar_df=chamados_para_exportar_df[chamados_para_exportar_df['UNIDADE']==unidade_selecionada]
    if status_chamado_selecionado and 'STATUS' in chamados_para_exportar_df.columns: chamados_para_exportar_df=chamados_para_exportar_df[chamados_para_exportar_df['STATUS']==status_chamado_selecionado]
    output=io.BytesIO()
    with pd.ExcelWriter(output,engine='xlsxwriter') as writer:
        colunas_principais=['CHAMADO','TITULO','SOLICITANTE','DEPARTAMENTO','UNIDADE','SERVICO','TEMA','TIPOCHAMADO','TEMPLATE','GRUPO','CATEGORIA','PRIORIDADE','ATENDENTE','DESCRICAO','PRAZO_HORAS','STATUS','CD_STATUS']
        datas_horas_formatadas={}; df_export_temp=chamados_para_exportar_df.copy()
        for col_raw in [c for c in df_export_temp.columns if '_RAW' in c and 'DT_' in c]:
            col_format_name=col_raw.replace('_RAW','').replace('DT_','DATA_')
            if col_raw in df_export_temp.columns: datas_horas_formatadas[col_format_name]=pd.to_datetime(df_export_temp[col_raw],errors='coerce').dt.strftime('%d-%m-%Y')
        for col_raw in [c for c in df_export_temp.columns if '_RAW' in c and 'HORA_' in c]:
            col_format_name=col_raw.replace('_RAW','')
            if col_raw in df_export_temp.columns: datas_horas_formatadas[col_format_name]=df_export_temp[col_raw].astype(str).apply(lambda x: x.split()[-1] if ' ' in x else x)
        df_export_final=df_export_temp[[col for col in colunas_principais if col in df_export_temp.columns]]
        for col_name,col_data in datas_horas_formatadas.items(): df_export_final[col_name]=col_data
        df_export_final.to_excel(writer,index=False,sheet_name='Chamados')
        workbook=writer.book; worksheet=writer.sheets['Chamados']
        for i,col in enumerate(df_export_final.columns):
            column_len=df_export_final[col].astype(str).map(len).max()
            column_len=max(column_len,len(col)) if not pd.isna(column_len) else len(col)
            worksheet.set_column(i,i,min(column_len+2,50))
    excel_data=output.getvalue()
    filename=f"chamados_exportados_{date.today().strftime('%Y%m%d')}.xlsx"
    return Response(excel_data,mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment;filename={filename}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)