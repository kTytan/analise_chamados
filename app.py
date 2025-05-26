# app.py
from flask import Flask, render_template, request, url_for, Response
from data_handler import (
    get_chamados, get_distinct_servicos, get_distinct_tipos_chamado,
    get_distinct_grupos_solucao, get_distinct_unidades, get_distinct_status_chamado
)
from datetime import date, timedelta, datetime
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

SERVICO_ORACLE = "1-SISTEMAS (ERP Oracle)" # Conforme sua última atualização
GRUPO_SUSTENTACAO_SEVEN = "Sustentação - SEVEN"
GRUPO_SUSTENTACAO_MMBIT = "Solution - MMBIT" # Conforme sua última atualização
GRUPO_AGUARDANDO_AVALIACAO = "Aguardando Avaliação"
# PRIORIDADES_CRITICAS_ALTAS = ['Crítica', 'Alta', 'Média', 'Baixa'] # Conforme sua última atualização, ajuste se o KPI for só para Crítica/Alta
PRIORIDADES_CRITICAS_ALTAS = ['Crítica', 'Alta'] # Mantendo foco em Crítica/Alta para o KPI específico

TIPO_CHAMADO_INCIDENTE = "Incidente" 
TIPO_CHAMADO_REQUISICAO_SERVICO = "Requisição de Serviço" 

# Status baseados na sua imagem - VERIFIQUE E AJUSTE OS NOMES EXATOS
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

# Listas para Agrupar Status para KPIs "Em Atendimento" (agrupado) e "Fechados"
STATUS_EM_ATENDIMENTO_LISTA = [
    STATUS_NOVO_SEM_CATEGORIA, STATUS_EM_ATENDIMENTO_ESPECIFICO, STATUS_AGENDADO,
    STATUS_ENCAMINHADO_FORNECEDOR, STATUS_AGUARDANDO_APROVACAO, STATUS_AGENDADO_COM_FORNECEDOR
]
STATUS_FECHADO_LISTA = [
    STATUS_ENCERRADO, STATUS_FECHADO_PELO_USUARIO, STATUS_FECHADO_PELO_ADMIN_AREA,
    STATUS_FECHADO_DECURSO_PRAZO, STATUS_FINALIZADO_PELO_FORNECEDOR
]

# Cores para as Fatias da Pizza Agrupada (usada em gerar_kpis_e_pizza)
CORES_KPI_PIZZA = {
    'Em Atendimento': 'orange',
    'Fechados': 'green',
    STATUS_AGUARDANDO_SOLICITANTE: '#007bff',
    STATUS_CONTESTADO: '#ffc107',
    STATUS_REPROVADO: '#dc3545'
}
# Cores para a Pizza Detalhada da Página Index (pode incluir mais status)
CORES_INDEX_PIZZA = {**CORES_KPI_PIZZA, **{ # Começa com as cores agrupadas e adiciona/sobrescreve
    STATUS_NOVO_SEM_CATEGORIA: '#add8e6', STATUS_EM_ATENDIMENTO_ESPECIFICO: '#87ceeb',
    STATUS_ENCERRADO: '#28a745', STATUS_FECHADO_PELO_USUARIO: '#218838',
    STATUS_FECHADO_PELO_ADMIN_AREA: '#1e7e34', STATUS_FECHADO_DECURSO_PRAZO: '#19692c',
    STATUS_AGENDADO: '#6495ed', STATUS_ENCAMINHADO_FORNECEDOR: '#4682b4',
    STATUS_AGUARDANDO_APROVACAO: '#5f9ea0', STATUS_AGENDADO_COM_FORNECEDOR: '#4169e1',
    STATUS_FINALIZADO_PELO_FORNECEDOR: '#228b22'
}}


def gerar_kpis_e_pizza(df_grupo_tipo, titulo_pizza, incluir_plotly_js_para_este_grafico=False):
    kpis = {'total': 0, 'em_atendimento': 0, 'fechados': 0, 
            'aguardando_solicitante': 0, 'contestado': 0, 'reprovado': 0}
    pizza_html = None
    if not df_grupo_tipo.empty and 'STATUS' in df_grupo_tipo.columns:
        kpis['total'] = len(df_grupo_tipo)
        kpis['em_atendimento'] = len(df_grupo_tipo[df_grupo_tipo['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)])
        kpis['fechados'] = len(df_grupo_tipo[df_grupo_tipo['STATUS'].isin(STATUS_FECHADO_LISTA)])
        kpis['aguardando_solicitante'] = len(df_grupo_tipo[df_grupo_tipo['STATUS'] == STATUS_AGUARDANDO_SOLICITANTE])
        kpis['contestado'] = len(df_grupo_tipo[df_grupo_tipo['STATUS'] == STATUS_CONTESTADO])
        kpis['reprovado'] = len(df_grupo_tipo[df_grupo_tipo['STATUS'] == STATUS_REPROVADO])
        
        pizza_data = {}
        if kpis['em_atendimento'] > 0: pizza_data['Em Atendimento'] = kpis['em_atendimento']
        if kpis['fechados'] > 0: pizza_data['Fechados'] = kpis['fechados']
        if kpis['aguardando_solicitante'] > 0: pizza_data[STATUS_AGUARDANDO_SOLICITANTE] = kpis['aguardando_solicitante']
        if kpis['contestado'] > 0: pizza_data[STATUS_CONTESTADO] = kpis['contestado']
        if kpis['reprovado'] > 0: pizza_data[STATUS_REPROVADO] = kpis['reprovado']

        if pizza_data:
            pizza_df = pd.DataFrame(list(pizza_data.items()), columns=['Status Agrupado', 'Contagem'])
            fig = px.pie(pizza_df, names='Status Agrupado', values='Contagem', 
                         title=titulo_pizza if titulo_pizza else None, hole=0.3,
                         color='Status Agrupado', color_discrete_map=CORES_KPI_PIZZA)
            fig.update_layout(
                margin=dict(l=5, r=5, t=30, b=5), height=220,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD',
                legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5, font=dict(size=9)), 
                title_font_size=12, title_x=0.5, title_xanchor='center'
            )
            pizza_html = fig.to_html(full_html=False, include_plotlyjs=incluir_plotly_js_para_este_grafico)
    return kpis, pizza_html

@app.route('/')
def index():
    # ... (sua lógica da rota index como na última versão que te enviei)
    # A principal mudança aqui é usar CORES_INDEX_PIZZA para o fig_status
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
    # ... (sua lógica da rota analise_detalhada como na última versão) ...
    # Lembre-se que lista_status_chamado é populada por get_distinct_status_chamado()
    # Os gráficos nesta página não foram alterados para o esquema de cores escuro ou para usar gerar_kpis_e_pizza.
    # Se precisar, podemos refatorá-los.
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
        if 'GRUPO' in chamados_filtrados_df.columns:
            grupo_counts = chamados_filtrados_df['GRUPO'].value_counts().nlargest(TOP_N_GRUPOS)
            if not grupo_counts.empty:
                fig_grupo = px.bar(grupo_counts, x=grupo_counts.index, y=grupo_counts.values, title=f'Top {TOP_N_GRUPOS} Grupos', labels={'y': 'Nº Chamados', 'index': 'Grupo'}, text=grupo_counts.values)
                fig_grupo.update_layout(margin=dict(l=20,r=20,t=50,b=20), height=400); fig_grupo.update_xaxes(tickangle=-45)
                grupo_graph_html = fig_grupo.to_html(full_html=False, include_plotlyjs='cdn'); primeiro_grafico_js_carregado_analise = True
        # ... (Adapte os outros 5 blocos de gráfico da analise_detalhada similarmente, gerenciando 'primeiro_grafico_js_carregado_analise') ...
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
    # ... (função como na sua última versão, mas usando gerar_kpis_e_pizza para a pizza geral
    #      e as constantes de status e CORES_KPI_PIZZA.
    #      Também renomeando variáveis _abertos_ para _em_atendimento_ e ajustando títulos.)
    print("--- ROTA /dashboard_tv_oracle: INÍCIO (Mês Atual) ---")
    servico_filtro_oracle = SERVICO_ORACLE
    hoje = date.today() 
    primeiro_dia_mes_atual = hoje.replace(day=1)
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    ultimo_dia_mes_atual = hoje.replace(day=dias_no_mes)
    data_inicio_str = primeiro_dia_mes_atual.strftime('%Y-%m-%d')
    data_fim_str = ultimo_dia_mes_atual.strftime('%Y-%m-%d')
    todos_chamados_mes_atual_df = get_chamados(data_inicio=data_inicio_str,data_fim=data_fim_str,area_id=1)

    total_incidentes_oracle_mes_todos_status = 0
    em_atendimento_incidentes_oracle_mes = 0 
    fechados_incidentes_oracle_mes = 0
    pizza_geral_oracle_status_html = None
    abertos_incidentes_aguardando_aval_mes = 0
    depto_em_atendimento_oracle_graph_html = None 
    abertos_incidentes_criticos_altos_oracle_mes = 0
    prioridade_em_atendimento_oracle_graph_html = None 
    primeiro_grafico_js_carregado_tv_oracle = False

    if not todos_chamados_mes_atual_df.empty:
        oracle_df_mes_atual = todos_chamados_mes_atual_df[todos_chamados_mes_atual_df['SERVICO'] == servico_filtro_oracle].copy()
        if not oracle_df_mes_atual.empty:
            oracle_incidentes_todos_status_mes_df = pd.DataFrame()
            if 'TIPOCHAMADO' in oracle_df_mes_atual.columns:
                oracle_incidentes_todos_status_mes_df = oracle_df_mes_atual[oracle_df_mes_atual['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()

            if not oracle_incidentes_todos_status_mes_df.empty and 'STATUS' in oracle_incidentes_todos_status_mes_df.columns:
                kpis_geral, pizza_html_geral = gerar_kpis_e_pizza(oracle_incidentes_todos_status_mes_df, 'Status Incidentes Oracle (Mês)', incluir_plotly_js_para_este_grafico='cdn')
                total_incidentes_oracle_mes_todos_status = kpis_geral['total']
                em_atendimento_incidentes_oracle_mes = kpis_geral['em_atendimento']
                fechados_incidentes_oracle_mes = kpis_geral['fechados']
                pizza_geral_oracle_status_html = pizza_html_geral
                if pizza_geral_oracle_status_html: primeiro_grafico_js_carregado_tv_oracle = True
                
                oracle_incidentes_em_atendimento_df = oracle_incidentes_todos_status_mes_df[oracle_incidentes_todos_status_mes_df['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)].copy()
                if not oracle_incidentes_em_atendimento_df.empty:
                    if 'GRUPO' in oracle_incidentes_em_atendimento_df.columns:
                        df_abertos_aguardando_aval = oracle_incidentes_em_atendimento_df[(oracle_incidentes_em_atendimento_df['GRUPO'] == GRUPO_AGUARDANDO_AVALIACAO) & (oracle_incidentes_em_atendimento_df['STATUS'] == STATUS_AGUARDANDO_SOLICITANTE)]
                        abertos_incidentes_aguardando_aval_mes = len(df_abertos_aguardando_aval)
                    if 'PRIORIDADE' in oracle_incidentes_em_atendimento_df.columns:
                        criticos_altos_df = oracle_incidentes_em_atendimento_df[oracle_incidentes_em_atendimento_df['PRIORIDADE'].isin(PRIORIDADES_CRITICAS_ALTAS)]
                        abertos_incidentes_criticos_altos_oracle_mes = len(criticos_altos_df)
                        prioridade_counts = oracle_incidentes_em_atendimento_df['PRIORIDADE'].value_counts()
                        if not prioridade_counts.empty:
                            fig_prioridade = px.bar(prioridade_counts, x=prioridade_counts.index, y=prioridade_counts.values, title='Incidentes "Em Atendimento" por Prioridade (Mês)', labels={'y': 'Nº Incidentes', 'index': 'Prioridade'}, text=prioridade_counts.values, color=prioridade_counts.index, color_discrete_map={'Crítica': '#d9534f', 'Alta': '#f0ad4e', 'Média': '#5bc0de', 'Baixa': '#5cb85c'})
                            fig_prioridade.update_layout(margin=dict(l=30,r=10,t=40,b=10), height=300, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD', title_font_size=12, title_x=0.5, title_xanchor='center')
                            fig_prioridade.update_xaxes(tickangle=-45); prioridade_em_atendimento_oracle_graph_html = fig_prioridade.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_tv_oracle)
                            if not primeiro_grafico_js_carregado_tv_oracle: primeiro_grafico_js_carregado_tv_oracle = True
                    if 'DEPARTAMENTO' in oracle_incidentes_em_atendimento_df.columns:
                        abertos_por_depto_counts = oracle_incidentes_em_atendimento_df['DEPARTAMENTO'].value_counts().nlargest(TOP_N_DEPTOS_ORACLE_TV)
                        if not abertos_por_depto_counts.empty:
                            fig_depto_abertos = px.bar(abertos_por_depto_counts, x=abertos_por_depto_counts.index, y=abertos_por_depto_counts.values, title=f'Top {TOP_N_DEPTOS_ORACLE_TV} Deptos com Incidentes "Em Atendimento" (Mês)', labels={'y': 'Nº Incidentes', 'index': 'Departamento'}, text=abertos_por_depto_counts.values)
                            fig_depto_abertos.update_layout(margin=dict(l=30,r=10,t=40,b=10), height=320, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD', title_font_size=12, title_x=0.5, title_xanchor='center')
                            fig_depto_abertos.update_xaxes(tickangle=-45); depto_em_atendimento_oracle_graph_html = fig_depto_abertos.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_tv_oracle)
                            # if not primeiro_grafico_js_carregado_tv_oracle: primeiro_grafico_js_carregado_tv_oracle = True # Último gráfico da página                            
    return render_template('dashboard_tv_oracle.html',
                           servico_foco=servico_filtro_oracle,
                           total_incidentes_oracle_mes_todos_status=total_incidentes_oracle_mes_todos_status,
                           em_atendimento_incidentes_oracle_mes=em_atendimento_incidentes_oracle_mes, 
                           fechados_incidentes_oracle_mes=fechados_incidentes_oracle_mes,
                           pizza_geral_oracle_status_html=pizza_geral_oracle_status_html,
                           abertos_incidentes_aguardando_aval_mes=abertos_incidentes_aguardando_aval_mes,
                           abertos_incidentes_criticos_altos_oracle_mes=abertos_incidentes_criticos_altos_oracle_mes,
                           prioridade_em_atendimento_oracle_graph_html=prioridade_em_atendimento_oracle_graph_html, 
                           depto_em_atendimento_oracle_graph_html=depto_em_atendimento_oracle_graph_html,      
                           data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                           )

@app.route('/dashboard_tv_fornecedores')
def dashboard_tv_fornecedores():
    # ... (função como na sua última versão, usando gerar_kpis_e_pizza e as novas chaves 'em_atendimento') ...
    # (ela já deve estar correta se a gerar_kpis_e_pizza estiver correta)
    print("--- ROTA /dashboard_tv_fornecedores: INÍCIO (Mês Atual) ---")
    hoje = date.today() 
    primeiro_dia_mes_atual = hoje.replace(day=1); dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    ultimo_dia_mes_atual = hoje.replace(day=dias_no_mes)
    data_inicio_str, data_fim_str = primeiro_dia_mes_atual.strftime('%Y-%m-%d'), ultimo_dia_mes_atual.strftime('%Y-%m-%d')
    todos_chamados_mes_atual_df = get_chamados(data_inicio=data_inicio_str,data_fim=data_fim_str,area_id=1)
    print(f"1. TV Fornecedores - Total chamados mês: {len(todos_chamados_mes_atual_df)}")
    dados_seven_incidentes = {'total':0,'em_atendimento':0,'fechados':0,'aguardando_solicitante':0,'contestado':0,'reprovado':0,'pizza_html':None}
    dados_seven_outros = {'total':0,'em_atendimento':0,'fechados':0,'aguardando_solicitante':0,'contestado':0,'reprovado':0,'pizza_html':None}
    dados_mmbit_incidentes = {'total':0,'em_atendimento':0,'fechados':0,'aguardando_solicitante':0,'contestado':0,'reprovado':0,'pizza_html':None}
    dados_mmbit_outros = {'total':0,'em_atendimento':0,'fechados':0,'aguardando_solicitante':0,'contestado':0,'reprovado':0,'pizza_html':None}
    primeiro_grafico_renderizado_fornecedores = False
    if not todos_chamados_mes_atual_df.empty and all(col in todos_chamados_mes_atual_df.columns for col in ['SERVICO', 'GRUPO', 'TIPOCHAMADO', 'STATUS']):
        seven_oracle_df = todos_chamados_mes_atual_df[(todos_chamados_mes_atual_df['SERVICO'] == SERVICO_ORACLE) & (todos_chamados_mes_atual_df['GRUPO'] == GRUPO_SUSTENTACAO_SEVEN)].copy()
        if not seven_oracle_df.empty:
            seven_incidentes_df = seven_oracle_df[seven_oracle_df['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(seven_incidentes_df, None, incluir_plotly_js_para_este_grafico='cdn' if not primeiro_grafico_renderizado_fornecedores else False)
            dados_seven_incidentes = {**kpis, 'pizza_html': pizza_html}; print(f"Seven Inc KPIs: {kpis}")
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True
            seven_outros_df = seven_oracle_df[seven_oracle_df['TIPOCHAMADO'] != TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(seven_outros_df, None, incluir_plotly_js_para_este_grafico=not primeiro_grafico_renderizado_fornecedores)
            dados_seven_outros = {**kpis, 'pizza_html': pizza_html}; print(f"Seven Outros KPIs: {kpis}")
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True
        mmbit_geral_df = todos_chamados_mes_atual_df[todos_chamados_mes_atual_df['GRUPO'] == GRUPO_SUSTENTACAO_MMBIT].copy()
        if not mmbit_geral_df.empty:
            mmbit_incidentes_df = mmbit_geral_df[mmbit_geral_df['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(mmbit_incidentes_df, None, incluir_plotly_js_para_este_grafico=not primeiro_grafico_renderizado_fornecedores)
            dados_mmbit_incidentes = {**kpis, 'pizza_html': pizza_html}; print(f"MMBIT Inc KPIs: {kpis}")
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True
            mmbit_outros_df = mmbit_geral_df[mmbit_geral_df['TIPOCHAMADO'] != TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(mmbit_outros_df, None, incluir_plotly_js_para_este_grafico=not primeiro_grafico_renderizado_fornecedores)
            dados_mmbit_outros = {**kpis, 'pizza_html': pizza_html}; print(f"MMBIT Outros KPIs: {kpis}")
    return render_template('dashboard_tv_fornecedores.html',
                           data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                           dados_seven_incidentes=dados_seven_incidentes, dados_seven_outros=dados_seven_outros,
                           dados_mmbit_incidentes=dados_mmbit_incidentes, dados_mmbit_outros=dados_mmbit_outros,
                           GRUPO_SUSTENTACAO_SEVEN_NOME=GRUPO_SUSTENTACAO_SEVEN,
                           GRUPO_SUSTENTACAO_MMBIT_NOME=GRUPO_SUSTENTACAO_MMBIT,
                           endpoint='dashboard_tv_fornecedores')

@app.route('/exportar_excel')
def exportar_excel():
    # ... (função como na sua última versão, garantindo que usa 'STATUS' e não 'STATUS_CHAMADO' para filtrar) ...
    print("Acessando rota /exportar_excel")
    data_inicio_form = request.args.get('data_inicio'); data_fim_form = request.args.get('data_fim')
    servico_selecionado = request.args.get('servico', ''); tipo_chamado_selecionado = request.args.get('tipo_chamado', '')
    grupo_solucao_selecionado = request.args.get('grupo_solucao', ''); unidade_selecionada = request.args.get('unidade', '')            
    status_chamado_selecionado = request.args.get('status_chamado', ''); area_id_param = request.args.get('area_id', 1, type=int)
    if data_inicio_form and data_fim_form: data_inicio_str, data_fim_str = data_inicio_form, data_fim_form
    else:
        data_fim_dt = date.today(); data_inicio_dt = data_fim_dt - timedelta(days=29)
        data_inicio_str, data_fim_str = data_inicio_dt.strftime('%Y-%m-%d'), data_fim_dt.strftime('%Y-%m-%d')
    chamados_para_exportar_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=area_id_param)
    if servico_selecionado and 'SERVICO' in chamados_para_exportar_df.columns: chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['SERVICO'] == servico_selecionado]
    if tipo_chamado_selecionado and 'TIPOCHAMADO' in chamados_para_exportar_df.columns: chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['TIPOCHAMADO'] == tipo_chamado_selecionado]
    if grupo_solucao_selecionado and 'GRUPO' in chamados_para_exportar_df.columns: chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['GRUPO'] == grupo_solucao_selecionado]
    if unidade_selecionada and 'UNIDADE' in chamados_para_exportar_df.columns: chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['UNIDADE'] == unidade_selecionada]
    if status_chamado_selecionado and 'STATUS' in chamados_para_exportar_df.columns: chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['STATUS'] == status_chamado_selecionado]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        colunas_principais = ['CHAMADO','TITULO','SOLICITANTE','DEPARTAMENTO','UNIDADE','SERVICO','TEMA','TIPOCHAMADO','TEMPLATE','GRUPO','CATEGORIA','PRIORIDADE','ATENDENTE','DESCRICAO','PRAZO_HORAS','STATUS','CD_STATUS']
        datas_horas_formatadas = {}
        df_export_temp = chamados_para_exportar_df.copy()
        for col_raw in [c for c in df_export_temp.columns if '_RAW' in c and 'DT_' in c]:
            col_format_name = col_raw.replace('_RAW', '').replace('DT_', 'DATA_')
            if col_raw in df_export_temp.columns: datas_horas_formatadas[col_format_name] = pd.to_datetime(df_export_temp[col_raw], errors='coerce').dt.strftime('%d-%m-%Y')
        for col_raw in [c for c in df_export_temp.columns if '_RAW' in c and 'HORA_' in c]:
            col_format_name = col_raw.replace('_RAW', '')
            if col_raw in df_export_temp.columns: datas_horas_formatadas[col_format_name] = df_export_temp[col_raw].astype(str).apply(lambda x: x.split()[-1] if ' ' in x else x)
        df_export_final = df_export_temp[[col for col in colunas_principais if col in df_export_temp.columns]]
        for col_name, col_data in datas_horas_formatadas.items(): df_export_final[col_name] = col_data
        df_export_final.to_excel(writer, index=False, sheet_name='Chamados')
        workbook  = writer.book; worksheet = writer.sheets['Chamados']
        for i, col in enumerate(df_export_final.columns):
            column_len = df_export_final[col].astype(str).map(len).max()
            column_len = max(column_len, len(col)) if not pd.isna(column_len) else len(col)
            worksheet.set_column(i, i, min(column_len + 2, 50))
    excel_data = output.getvalue()
    filename = f"chamados_exportados_{date.today().strftime('%Y%m%d')}.xlsx"
    return Response(excel_data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment;filename={filename}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)