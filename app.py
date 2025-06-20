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

# --- Constantes Globais (COMO NO SEU ÚLTIMO ENVIO) ---
ITEMS_PER_PAGE = 50
TOP_N_DEPARTAMENTOS = 10; TOP_N_GRUPOS = 10; TOP_N_UNIDADES = 10; TOP_N_SERVICOS = 10
TOP_N_DEPTOS_ORACLE_TV = 10

SERVICO_ORACLE = "1-SISTEMAS (ERP Oracle)" 
GRUPO_SUSTENTACAO_SEVEN = "Sustentação - SEVEN"
GRUPO_SUSTENTACAO_MMBIT = "Solution - MMBIT" 
GRUPO_AGUARDANDO_AVALIACAO = "Aguardando Avaliação"
GRUPO_DBP_PB_AMERICA = "DBP - PB América"
GRUPO_DBP_SOLUTION = "DBP - Solution"
GRUPO_DBP_POINTER = "DBP - Pointer"
GRUPO_DBP_PB_SHOP = "DBP - PB Shop"
GRUPO_DBP_CYBER_PRO = "DBP - Cyber Pro"
GRUPO_DBP_EVOLUTION = "DBP - Evolution"
GRUPO_DBP_ANALYTICS = "DBP - Analytics"
GRUPO_DBP_OMNI = "DBP - Omni"
PRIORIDADES_CRITICAS_ALTAS = ['Crítica', 'Alta'] 

TIPO_CHAMADO_INCIDENTE = "Incidente" 
TIPO_CHAMADO_REQUISICAO_SERVICO = "Requisição de Serviço" 

STATUS_NOVO_SEM_CATEGORIA = "Novo (sem categoria)"; STATUS_EM_ATENDIMENTO_ESPECIFICO = "Em atendimento" 
STATUS_ENCERRADO = "Encerrado"; STATUS_FECHADO_PELO_USUARIO = "Fechado pelo usuário"
STATUS_FECHADO_PELO_ADMIN_AREA = "Fechado pelo administrador da área"; STATUS_CONTESTADO = "Contestado"
STATUS_FECHADO_DECURSO_PRAZO = "Fechado por decurso de prazo"; STATUS_AGENDADO = "Agendado"
STATUS_AGUARDANDO_SOLICITANTE = "Aguardando solicitante"; STATUS_ENCAMINHADO_FORNECEDOR = "Encaminhado para fornecedor"
STATUS_AGUARDANDO_APROVACAO = "Aguardando aprovação"; STATUS_REPROVADO = "Reprovado"
STATUS_AGENDADO_COM_FORNECEDOR = "Agendado com fornecedor"; STATUS_FINALIZADO_PELO_FORNECEDOR = "Finalizado pelo fornecedor"

STATUS_EM_ATENDIMENTO_LISTA = [STATUS_NOVO_SEM_CATEGORIA, STATUS_EM_ATENDIMENTO_ESPECIFICO, STATUS_AGENDADO, STATUS_ENCAMINHADO_FORNECEDOR, STATUS_AGUARDANDO_APROVACAO, STATUS_AGENDADO_COM_FORNECEDOR]
STATUS_FECHADO_LISTA = [STATUS_ENCERRADO, STATUS_FECHADO_PELO_USUARIO, STATUS_FECHADO_PELO_ADMIN_AREA, STATUS_FECHADO_DECURSO_PRAZO, STATUS_FINALIZADO_PELO_FORNECEDOR]
LISTA_GRUPOS_DBP = [GRUPO_DBP_PB_AMERICA, GRUPO_DBP_SOLUTION, GRUPO_DBP_POINTER,GRUPO_DBP_PB_SHOP, GRUPO_DBP_CYBER_PRO, GRUPO_DBP_EVOLUTION,GRUPO_DBP_ANALYTICS, GRUPO_DBP_OMNI]
CORES_KPI_PIZZA = {'Em Atendimento': 'orange', STATUS_AGUARDANDO_SOLICITANTE: '#007bff', STATUS_CONTESTADO: '#ffc107', STATUS_NOVO_SEM_CATEGORIA: '#add8e6', STATUS_EM_ATENDIMENTO_ESPECIFICO : '#87ceeb', STATUS_AGENDADO: '#6495ed', STATUS_ENCAMINHADO_FORNECEDOR: '#4682b4', STATUS_AGUARDANDO_APROVACAO: '#5f9ea0', STATUS_AGENDADO_COM_FORNECEDOR: '#4169e1'}
CORES_INDEX_PIZZA = {**CORES_KPI_PIZZA, **{'Fechados': 'green', STATUS_ENCERRADO: '#28a745', STATUS_FECHADO_PELO_USUARIO: '#218838', STATUS_FECHADO_PELO_ADMIN_AREA: '#1e7e34', STATUS_FECHADO_DECURSO_PRAZO: '#19692c', STATUS_FINALIZADO_PELO_FORNECEDOR: '#228b22', STATUS_REPROVADO: '#dc3545'}}

def gerar_kpis_e_pizza(df_segmento, titulo_pizza, plotly_js_config='cdn'):
    kpis = {
        'total_em_aberto': 0, 'em_atendimento': 0, 'aguardando_solicitante': 0,
        'contestado': 0, 'sla_estourado': 0, 'abertos_7_dias_mais': 0
    }
    pizza_html = None
    if df_segmento is None or df_segmento.empty: return kpis, pizza_html

    required_cols_base = ['STATUS', 'DT_ABERTURA_RAW', 'HORA_ABERTURA_RAW']; required_cols_sla = ['sla_atendimento_tempo_decorrido', 'sla_encaminhamento_tempo_decorrido', 'sla_atendimento_tempo_definido']
    if not all(col in df_segmento.columns for col in required_cols_base):
        # Retorna o dicionário de kpis zerados, sem 'total_criados' pois foi removido
        return kpis, pizza_html

    df_nao_finalizados = df_segmento[
        ~df_segmento['STATUS'].isin(STATUS_FECHADO_LISTA) &
        (df_segmento['STATUS'] != STATUS_REPROVADO)
    ].copy()

    if not df_nao_finalizados.empty:
        kpis['em_atendimento'] = len(df_nao_finalizados[df_nao_finalizados['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)])
        kpis['aguardando_solicitante'] = len(df_nao_finalizados[df_nao_finalizados['STATUS'] == STATUS_AGUARDANDO_SOLICITANTE])
        kpis['contestado'] = len(df_nao_finalizados[df_nao_finalizados['STATUS'] == STATUS_CONTESTADO])
        
        # Calcular o novo KPI "Total em Aberto"
        kpis['total_em_aberto'] = kpis['em_atendimento'] + kpis['aguardando_solicitante'] + kpis['contestado']
        
        if all(col in df_nao_finalizados.columns for col in required_cols_sla):
            decorrido_atend = pd.to_numeric(df_nao_finalizados['sla_atendimento_tempo_decorrido'], errors='coerce').fillna(0); decorrido_encam = pd.to_numeric(df_nao_finalizados['sla_encaminhamento_tempo_decorrido'], errors='coerce').fillna(0)
            definido_atend_num = pd.to_numeric(df_nao_finalizados['sla_atendimento_tempo_definido'], errors='coerce').fillna(0)
            total_decorrido_atend = decorrido_atend + decorrido_encam
            df_com_sla_valido = df_nao_finalizados[definido_atend_num > 0].copy()
            if not df_com_sla_valido.empty:
                total_decorrido_subset = pd.to_numeric(df_com_sla_valido['sla_atendimento_tempo_decorrido'], errors='coerce').fillna(0) + pd.to_numeric(df_com_sla_valido['sla_encaminhamento_tempo_decorrido'], errors='coerce').fillna(0)
                definido_subset = pd.to_numeric(df_com_sla_valido['sla_atendimento_tempo_definido'], errors='coerce').fillna(0)
                kpis['sla_estourado'] = len(df_com_sla_valido[total_decorrido_subset > definido_subset])
        
        if 'DT_ABERTURA_RAW' in df_nao_finalizados.columns:
            df_temp_dates = df_nao_finalizados.copy(); df_temp_dates.loc[:, 'DT_ABERTURA_DATETIME'] = pd.to_datetime(df_temp_dates['DT_ABERTURA_RAW'], errors='coerce'); df_temp_dates.dropna(subset=['DT_ABERTURA_DATETIME'], inplace=True)
            if not df_temp_dates.empty: agora_naive = datetime.now(); df_temp_dates.loc[:, 'IDADE_CHAMADO'] = agora_naive - df_temp_dates['DT_ABERTURA_DATETIME']; kpis['abertos_7_dias_mais'] = len(df_temp_dates[df_temp_dates['IDADE_CHAMADO'] >= timedelta(days=7)])
        
        pizza_display_data = {}
        if kpis['em_atendimento'] > 0: pizza_display_data['Em Atendimento'] = kpis['em_atendimento']
        if kpis['aguardando_solicitante'] > 0: pizza_display_data[STATUS_AGUARDANDO_SOLICITANTE] = kpis['aguardando_solicitante']
        if kpis['contestado'] > 0: pizza_display_data[STATUS_CONTESTADO] = kpis['contestado']
        outros_status_ativos = df_nao_finalizados[~df_nao_finalizados['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA) & (df_nao_finalizados['STATUS'] != STATUS_AGUARDANDO_SOLICITANTE) & (df_nao_finalizados['STATUS'] != STATUS_CONTESTADO)]['STATUS'].value_counts()
        for status_nome, contagem in outros_status_ativos.items():
            if contagem > 0: pizza_display_data[status_nome] = contagem
        if pizza_display_data:
            pizza_df_final = pd.DataFrame(list(pizza_display_data.items()), columns=['Status', 'Contagem'])
            if not pizza_df_final.empty and pizza_df_final['Contagem'].sum() > 0:
                fig = px.pie(pizza_df_final, names='Status', values='Contagem', title=titulo_pizza if titulo_pizza else None, hole=0.3, color='Status', color_discrete_map=CORES_KPI_PIZZA) 
                fig.update_layout(margin=dict(l=5,r=5,t=10,b=20), height=170, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD', legend=dict(orientation="h",yanchor="bottom",y=-0.3,xanchor="center",x=0.5,font=dict(size=8)), title_font_size=10)
                pizza_html = fig.to_html(full_html=False, include_plotlyjs=plotly_js_config)
    return kpis, pizza_html


@app.route('/')
def index():
    print("Acessando rota / (index)"); data_inicio_form = request.args.get('data_inicio'); data_fim_form = request.args.get('data_fim'); page = request.args.get('page', 1, type=int)
    if data_inicio_form and data_fim_form: data_inicio_str, data_fim_str = data_inicio_form, data_fim_form
    else: data_fim_dt = date.today(); data_inicio_dt = data_fim_dt - timedelta(days=29); data_inicio_str, data_fim_str = data_inicio_dt.strftime('%Y-%m-%d'), data_fim_dt.strftime('%Y-%m-%d')
    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)
    total_chamados_filtrados = 0; chamados_pagina_df = pd.DataFrame(); total_pages = 0; status_graph_html = None; dept_graph_html = None; primeiro_grafico_js_carregado_index = False
    if not todos_chamados_df.empty:
        total_chamados_filtrados = len(todos_chamados_df); total_pages = math.ceil(total_chamados_filtrados / ITEMS_PER_PAGE)
        if page < 1: page = 1
        elif page > total_pages and total_pages > 0: page = total_pages
        start_index = (page - 1) * ITEMS_PER_PAGE; end_index = start_index + ITEMS_PER_PAGE
        chamados_pagina_df = todos_chamados_df.iloc[start_index:end_index].copy()
        if 'DT_ABERTURA_RAW' in chamados_pagina_df.columns: chamados_pagina_df.loc[:, 'DT_ABERTURA_FORMATADA'] = chamados_pagina_df['DT_ABERTURA_RAW'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notna(x) else '')
        if 'STATUS' in todos_chamados_df.columns:
            status_counts = todos_chamados_df['STATUS'].value_counts()
            if not status_counts.empty and status_counts.sum() > 0:
                fig_status = px.pie(status_counts, names=status_counts.index, values=status_counts.values, title='Distribuição de Chamados por Status', color_discrete_map=CORES_INDEX_PIZZA)
                fig_status.update_layout(margin=dict(l=20,r=20,t=40,b=20), height=330, title_font_size=14, legend=dict(font=dict(size=10)))
                status_graph_html = fig_status.to_html(full_html=False, include_plotlyjs='cdn'); primeiro_grafico_js_carregado_index = True
        if 'DEPARTAMENTO' in todos_chamados_df.columns:
            dept_counts = todos_chamados_df['DEPARTAMENTO'].value_counts().nlargest(TOP_N_DEPARTAMENTOS)
            if not dept_counts.empty:
                fig_dept = px.bar(dept_counts, x=dept_counts.index, y=dept_counts.values, title=f'Top {TOP_N_DEPARTAMENTOS} Departamentos', labels={'y': 'Nº de Chamados', 'index': 'Departamento'}, text=dept_counts.values)
                fig_dept.update_layout(margin=dict(l=20,r=20,t=50,b=20), height=400); fig_dept.update_xaxes(tickangle=-45)
                dept_graph_html = fig_dept.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_index)
    return render_template('index.html', chamados=chamados_pagina_df, data_inicio=data_inicio_str, data_fim=data_fim_str, total_chamados=total_chamados_filtrados, page=page, total_pages=total_pages, items_per_page=ITEMS_PER_PAGE, status_graph_html=status_graph_html, dept_graph_html=dept_graph_html, endpoint='index')

# --- ROTA ANALISE DETALHADA (COM FILTRO MÚLTIPLO DE STATUS) ---
@app.route('/analise_detalhada')
def analise_detalhada():
    print("Acessando rota /analise_detalhada")
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')
    servico_selecionado_filtro = request.args.get('servico', '')
    tipo_chamado_selecionado_filtro = request.args.get('tipo_chamado', '')
    grupo_solucao_selecionado = request.args.get('grupo_solucao', '')
    unidade_selecionada = request.args.get('unidade', '')
    
    status_selecionados_lista_url = request.args.getlist('status_chamado') # Pega lista da URL
    status_chamado_form = request.args.get('status_chamado', '') # Pega filtro único do form

    page = request.args.get('page', 1, type=int)

    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        data_fim_dt = date.today(); data_inicio_dt = date(2000, 1, 1) # Padrão histórico amplo
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d'); data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    lista_servicos_df = get_distinct_servicos(); lista_tipos_chamado_df = get_distinct_tipos_chamado(); lista_grupos_solucao_df = get_distinct_grupos_solucao(); lista_unidades_df = get_distinct_unidades()
    lista_status_para_dropdown = get_distinct_status_chamado()

    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)
    
    chamados_filtrados_df = todos_chamados_df.copy()
    if servico_selecionado_filtro and 'SERVICO' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['SERVICO'] == servico_selecionado_filtro]
    if tipo_chamado_selecionado_filtro and 'TIPOCHAMADO' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['TIPOCHAMADO'] == tipo_chamado_selecionado_filtro]
    if grupo_solucao_selecionado and 'GRUPO' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['GRUPO'] == grupo_solucao_selecionado]
    if unidade_selecionada and 'UNIDADE' in chamados_filtrados_df.columns: chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['UNIDADE'] == unidade_selecionada]
    
    status_validos_para_filtro = [s for s in status_selecionados_lista_url if s]
    status_para_exibir_no_dropdown = ''

    if status_validos_para_filtro and 'STATUS' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['STATUS'].isin(status_validos_para_filtro)]
        if len(status_validos_para_filtro) == 1:
            status_para_exibir_no_dropdown = status_validos_para_filtro[0]
    elif status_chamado_form and 'STATUS' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['STATUS'] == status_chamado_form]
        status_para_exibir_no_dropdown = status_chamado_form
    
    # Inicialização de variáveis antes do bloco 'if'
    chamados_pagina_df = pd.DataFrame() # <<< CORREÇÃO AQUI
    total_chamados_final = 0; total_pages = 0;
    grupo_graph_html = None; unidade_graph_html = None; servico_graph_html = None; tipo_chamado_graph_html = None; evolucao_mensal_geral_graph_html = None; evolucao_tipo_graph_html = None
    primeiro_grafico_js_carregado_analise = False

    if not chamados_filtrados_df.empty:
        total_chamados_final = len(chamados_filtrados_df); total_pages = math.ceil(total_chamados_final / ITEMS_PER_PAGE)
        if page < 1: page = 1
        elif page > total_pages and total_pages > 0: page = total_pages
        start_index = (page - 1) * ITEMS_PER_PAGE; end_index = start_index + ITEMS_PER_PAGE
        chamados_pagina_df = chamados_filtrados_df.iloc[start_index:end_index].copy()
        if 'DT_ABERTURA_RAW' in chamados_pagina_df.columns: chamados_pagina_df.loc[:, 'DT_ABERTURA_FORMATADA'] = chamados_pagina_df['DT_ABERTURA_RAW'].apply(lambda x: x.strftime('%d-%m-%Y') if pd.notna(x) else '')
        
        # Lógica de geração de todos os 6 gráficos
        if 'GRUPO' in chamados_filtrados_df.columns:
            grupo_counts = chamados_filtrados_df['GRUPO'].value_counts().nlargest(TOP_N_GRUPOS)
            if not grupo_counts.empty:
                fig_grupo = px.bar(grupo_counts, x=grupo_counts.index, y=grupo_counts.values, title=f'Top {TOP_N_GRUPOS} Grupos', labels={'y': 'Nº Chamados', 'index': 'Grupo'}, text=grupo_counts.values)
                fig_grupo.update_layout(margin=dict(l=20,r=20,t=50,b=20), height=400); fig_grupo.update_xaxes(tickangle=-45)
                grupo_graph_html = fig_grupo.to_html(full_html=False, include_plotlyjs='cdn'); primeiro_grafico_js_carregado_analise = True
        
        # ... (CÓDIGO COMPLETO PARA OS OUTROS 5 GRÁFICOS DEVE ESTAR AQUI NO SEU ARQUIVO, gerenciando a flag 'primeiro_grafico_js_carregado_analise')
    
    return render_template('analise_detalhada.html',
                           chamados=chamados_pagina_df, data_inicio=data_inicio_str, data_fim=data_fim_str,
                           servicos=lista_servicos_df.to_dict(orient='records'),
                           tipos_chamado=lista_tipos_chamado_df.to_dict(orient='records'),
                           grupos_solucao=lista_grupos_solucao_df.to_dict(orient='records'),
                           unidades=lista_unidades_df.to_dict(orient='records'),
                           lista_status_chamado=lista_status_para_dropdown,
                           servico_selecionado=servico_selecionado_filtro,
                           tipo_chamado_selecionado=tipo_chamado_selecionado_filtro,
                           grupo_solucao_selecionado=grupo_solucao_selecionado,
                           unidade_selecionada=unidade_selecionada,
                           status_chamado_selecionado=status_para_exibir_no_dropdown,
                           total_chamados=total_chamados_final,
                           page=page, total_pages=total_pages, items_per_page=ITEMS_PER_PAGE,
                           grupo_graph_html=grupo_graph_html, unidade_graph_html=unidade_graph_html,
                           servico_graph_html=servico_graph_html, tipo_chamado_graph_html=tipo_chamado_graph_html,
                           evolucao_mensal_geral_graph_html=evolucao_mensal_geral_graph_html,
                           evolucao_tipo_graph_html=evolucao_tipo_graph_html,
                           endpoint='analise_detalhada')

# --- ROTA DASHBOARD TV ORACLE ---
@app.route('/dashboard_tv_oracle')
def dashboard_tv_oracle():
    # ... (Código COMPLETO da rota como na última versão, que já estava corrigida) ...
    print("--- ROTA /dashboard_tv_oracle: INÍCIO (Mês Atual - Incidentes vs Não Incidentes) ---")
    servico_filtro_oracle = SERVICO_ORACLE; hoje = date.today() 
    primeiro_dia_mes_atual = hoje.replace(day=1); dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]; ultimo_dia_mes_atual = hoje.replace(day=dias_no_mes); data_inicio_str = primeiro_dia_mes_atual.strftime('%Y-%m-%d'); data_fim_str = ultimo_dia_mes_atual.strftime('%Y-%m-%d')
    todos_chamados_mes_atual_df = get_chamados(data_inicio=data_inicio_str,data_fim=data_fim_str,area_id=1)
    kpi_total_incidentes_criados=0;kpi_incidentes_fechados=0;kpi_incidentes_em_atendimento=0;kpi_incidentes_aguard_solic=0;kpi_incidentes_contestados=0;kpi_incidentes_aguard_aval_grupo=0;kpi_incidentes_aging_medio_ativos_str="N/A";kpi_incidentes_abertos_sem_atendente=0;kpi_incidentes_tempo_medio_atend_fechados_str="N/A";pizza_incidentes_oracle_status_html=None
    kpi_total_nao_incidentes_criados=0;kpi_nao_incidentes_fechados=0;kpi_nao_incidentes_em_atendimento=0;kpi_nao_incidentes_aguard_solic=0;kpi_nao_incidentes_contestados=0;kpi_nao_incidentes_aguard_aval_grupo=0;kpi_nao_incidentes_aging_medio_ativos_str="N/A";kpi_nao_incidentes_abertos_sem_atendente=0;kpi_nao_incidentes_tempo_medio_atend_str="N/A";pizza_nao_incidentes_oracle_status_html=None
    primeiro_grafico_js_carregado_tv_oracle = False
    if not todos_chamados_mes_atual_df.empty:
        oracle_df_mes_atual=todos_chamados_mes_atual_df[todos_chamados_mes_atual_df['SERVICO']==servico_filtro_oracle].copy();cols_base_necessarias=['TIPOCHAMADO','STATUS','GRUPO','DT_ABERTURA_RAW','HORA_ABERTURA_RAW','ATENDENTE'];coluna_tempo_usada_para_media='TEMPO_RESOLUCAO_DECORRIDO'
        if not oracle_df_mes_atual.empty and all(col in oracle_df_mes_atual.columns for col in cols_base_necessarias) and coluna_tempo_usada_para_media in oracle_df_mes_atual.columns:
            oracle_incidentes_df=oracle_df_mes_atual[oracle_df_mes_atual['TIPOCHAMADO']==TIPO_CHAMADO_INCIDENTE].copy()
            if not oracle_incidentes_df.empty:
                kpi_total_incidentes_criados=len(oracle_incidentes_df);kpi_incidentes_fechados=len(oracle_incidentes_df[oracle_incidentes_df['STATUS'].isin(STATUS_FECHADO_LISTA)]);kpi_incidentes_em_atendimento=len(oracle_incidentes_df[oracle_incidentes_df['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)]);kpi_incidentes_aguard_solic=len(oracle_incidentes_df[oracle_incidentes_df['STATUS']==STATUS_AGUARDANDO_SOLICITANTE]);kpi_incidentes_contestados=len(oracle_incidentes_df[oracle_incidentes_df['STATUS']==STATUS_CONTESTADO])
                incidentes_ativos_df=oracle_incidentes_df[~oracle_incidentes_df['STATUS'].isin(STATUS_FECHADO_LISTA)&(oracle_incidentes_df['STATUS']!=STATUS_REPROVADO)].copy()
                if not incidentes_ativos_df.empty:
                    df_inc_aguard_aval=incidentes_ativos_df[(incidentes_ativos_df['GRUPO']==GRUPO_AGUARDANDO_AVALIACAO)&(incidentes_ativos_df['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA+[STATUS_AGUARDANDO_SOLICITANTE,STATUS_AGUARDANDO_APROVACAO,STATUS_CONTESTADO]))];kpi_incidentes_aguard_aval_grupo=len(df_inc_aguard_aval)
                    temp_aging_inc=incidentes_ativos_df.copy();temp_aging_inc.loc[:,'HORA_ABERTURA_TD_TEMP']=pd.to_timedelta(temp_aging_inc['HORA_ABERTURA_RAW'].astype(str),errors='coerce');temp_aging_inc.loc[:,'TIMESTAMP_ABERTURA']=pd.to_datetime(temp_aging_inc['DT_ABERTURA_RAW'])+temp_aging_inc['HORA_ABERTURA_TD_TEMP'];temp_aging_inc.dropna(subset=['TIMESTAMP_ABERTURA'],inplace=True)
                    if not temp_aging_inc.empty:agora_inc=datetime.now();temp_aging_inc.loc[:,'IDADE_CHAMADO_TD']=agora_inc-temp_aging_inc['TIMESTAMP_ABERTURA'];media_idade_td_inc=temp_aging_inc['IDADE_CHAMADO_TD'].mean()
                    if pd.notna(media_idade_td_inc):dias_inc=media_idade_td_inc.days;horas_inc=media_idade_td_inc.seconds//3600;kpi_incidentes_aging_medio_ativos_str=f"{dias_inc}d {horas_inc}h"
                    else:kpi_incidentes_aging_medio_ativos_str="N/A"
                    kpi_incidentes_abertos_sem_atendente=len(incidentes_ativos_df[incidentes_ativos_df['ATENDENTE'].isna()|(incidentes_ativos_df['ATENDENTE']=='')])
                incidentes_fechados_com_tempo_df=oracle_incidentes_df[(oracle_incidentes_df['STATUS'].isin(STATUS_FECHADO_LISTA))&(oracle_incidentes_df[coluna_tempo_usada_para_media].notna())].copy()
                if not incidentes_fechados_com_tempo_df.empty:
                    incidentes_fechados_com_tempo_df.loc[:,'TEMPO_RESOL_NUM']=pd.to_numeric(incidentes_fechados_com_tempo_df[coluna_tempo_usada_para_media],errors='coerce');incidentes_fechados_com_tempo_df.dropna(subset=['TEMPO_RESOL_NUM'],inplace=True)
                    if not incidentes_fechados_com_tempo_df.empty:media_tempo_original=incidentes_fechados_com_tempo_df['TEMPO_RESOL_NUM'].mean()
                    if pd.notna(media_tempo_original):total_minutos_int=int(round(media_tempo_original));horas=total_minutos_int//60;minutos=total_minutos_int%60;kpi_incidentes_tempo_medio_atend_fechados_str=f"{horas:02d}:{minutos:02d}h"
                status_counts_incidentes=oracle_incidentes_df['STATUS'].value_counts()
                if not status_counts_incidentes.empty and status_counts_incidentes.sum()>0:
                    fig_pizza_inc=px.pie(status_counts_incidentes,names=status_counts_incidentes.index,values=status_counts_incidentes.values,title=None,hole=0.3,color_discrete_map=CORES_INDEX_PIZZA)
                    fig_pizza_inc.update_layout(margin=dict(l=5,r=5,t=5,b=5),height=220,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#DDDDDD',legend=dict(orientation="h",yanchor="bottom",y=-0.4,xanchor="center",x=0.5,font=dict(size=9)),title_font_size=11)
                    pizza_incidentes_oracle_status_html=fig_pizza_inc.to_html(full_html=False,include_plotlyjs='cdn' if not primeiro_grafico_js_carregado_tv_oracle else False)
                    if pizza_incidentes_oracle_status_html and not primeiro_grafico_js_carregado_tv_oracle:primeiro_grafico_js_carregado_tv_oracle=True
            oracle_nao_incidentes_df=oracle_df_mes_atual[oracle_df_mes_atual['TIPOCHAMADO']!=TIPO_CHAMADO_INCIDENTE].copy()
            if not oracle_nao_incidentes_df.empty and 'STATUS' in oracle_nao_incidentes_df.columns:
                kpi_total_nao_incidentes_criados=len(oracle_nao_incidentes_df);kpi_nao_incidentes_fechados=len(oracle_nao_incidentes_df[oracle_nao_incidentes_df['STATUS'].isin(STATUS_FECHADO_LISTA)]);kpi_nao_incidentes_em_atendimento=len(oracle_nao_incidentes_df[oracle_nao_incidentes_df['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)]);kpi_nao_incidentes_aguard_solic=len(oracle_nao_incidentes_df[oracle_nao_incidentes_df['STATUS']==STATUS_AGUARDANDO_SOLICITANTE]);kpi_nao_incidentes_contestados=len(oracle_nao_incidentes_df[oracle_nao_incidentes_df['STATUS']==STATUS_CONTESTADO])
                nao_incidentes_ativos_df=oracle_nao_incidentes_df[~oracle_nao_incidentes_df['STATUS'].isin(STATUS_FECHADO_LISTA)&(oracle_nao_incidentes_df['STATUS']!=STATUS_REPROVADO)].copy()
                if not nao_incidentes_ativos_df.empty:
                    df_nao_inc_aguard_aval=nao_incidentes_ativos_df[(nao_incidentes_ativos_df['GRUPO']==GRUPO_AGUARDANDO_AVALIACAO)&(nao_incidentes_ativos_df['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA+[STATUS_AGUARDANDO_SOLICITANTE,STATUS_AGUARDANDO_APROVACAO,STATUS_CONTESTADO]))];kpi_nao_incidentes_aguard_aval_grupo=len(df_nao_inc_aguard_aval)
                    temp_aging_nao_inc=nao_incidentes_ativos_df.copy();temp_aging_nao_inc.loc[:,'HORA_ABERTURA_TD_TEMP']=pd.to_timedelta(temp_aging_nao_inc['HORA_ABERTURA_RAW'].astype(str),errors='coerce');temp_aging_nao_inc.loc[:,'TIMESTAMP_ABERTURA']=pd.to_datetime(temp_aging_nao_inc['DT_ABERTURA_RAW'])+temp_aging_nao_inc['HORA_ABERTURA_TD_TEMP'];temp_aging_nao_inc.dropna(subset=['TIMESTAMP_ABERTURA'],inplace=True)
                    if not temp_aging_nao_inc.empty:agora_nao_inc=datetime.now();temp_aging_nao_inc.loc[:,'IDADE_CHAMADO_TD']=agora_nao_inc-temp_aging_nao_inc['TIMESTAMP_ABERTURA'];media_idade_td_nao_inc=temp_aging_nao_inc['IDADE_CHAMADO_TD'].mean()
                    if pd.notna(media_idade_td_nao_inc):dias_nao_inc=media_idade_td_nao_inc.days;horas_nao_inc=media_idade_td_nao_inc.seconds//3600;kpi_nao_incidentes_aging_medio_ativos_str=f"{dias_nao_inc}d {horas_nao_inc}h"
                    else: kpi_nao_incidentes_aging_medio_ativos_str="N/A"
                    kpi_nao_incidentes_abertos_sem_atendente=len(nao_incidentes_ativos_df[nao_incidentes_ativos_df['ATENDENTE'].isna()|(nao_incidentes_ativos_df['ATENDENTE']=='')])
                if coluna_tempo_usada_para_media in oracle_nao_incidentes_df.columns:
                    temp_df_nao_inc_atend=oracle_nao_incidentes_df[oracle_nao_incidentes_df[coluna_tempo_usada_para_media].notna()].copy()
                    temp_df_nao_inc_atend.loc[:,'TEMPO_RESOL_NUM']=pd.to_numeric(temp_df_nao_inc_atend[coluna_tempo_usada_para_media],errors='coerce');temp_df_nao_inc_atend.dropna(subset=['TEMPO_RESOL_NUM'],inplace=True)
                    if not temp_df_nao_inc_atend.empty:media_tempo_original_nao_inc=temp_df_nao_inc_atend['TEMPO_RESOL_NUM'].mean()
                    if pd.notna(media_tempo_original_nao_inc):total_minutos_int_nao_inc=int(round(media_tempo_original_nao_inc));horas_nao_inc_atend=total_minutos_int_nao_inc//60;minutos_nao_inc_atend=total_minutos_int_nao_inc%60;kpi_nao_incidentes_tempo_medio_atend_str=f"{horas_nao_inc_atend:02d}:{minutos_nao_inc_atend:02d}h"
                status_counts_nao_inc=oracle_nao_incidentes_df['STATUS'].value_counts()
                if not status_counts_nao_inc.empty and status_counts_nao_inc.sum()>0:
                    fig_pizza_nao_inc=px.pie(status_counts_nao_inc,names=status_counts_nao_inc.index,values=status_counts_nao_inc.values,title=None,hole=0.3,color_discrete_map=CORES_INDEX_PIZZA)
                    fig_pizza_nao_inc.update_layout(margin=dict(l=5,r=5,t=5,b=5),height=220,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font_color='#DDDDDD',legend=dict(orientation="h",yanchor="bottom",y=-0.4,xanchor="center",x=0.5,font=dict(size=9)),title_font_size=11)
                    pizza_nao_incidentes_oracle_status_html=fig_pizza_nao_inc.to_html(full_html=False,include_plotlyjs=not primeiro_grafico_js_carregado_tv_oracle)
                    if pizza_nao_incidentes_oracle_status_html and not primeiro_grafico_js_carregado_tv_oracle:primeiro_grafico_js_carregado_tv_oracle=True
    return render_template('dashboard_tv_oracle.html',servico_foco=servico_filtro_oracle,kpi_total_incidentes_criados=kpi_total_incidentes_criados,kpi_incidentes_fechados=kpi_incidentes_fechados,kpi_incidentes_em_atendimento=kpi_incidentes_em_atendimento,kpi_incidentes_aguard_solic=kpi_incidentes_aguard_solic,kpi_incidentes_contestados=kpi_incidentes_contestados,kpi_incidentes_aguard_aval_grupo=kpi_incidentes_aguard_aval_grupo,kpi_incidentes_aging_medio_ativos_str=kpi_incidentes_aging_medio_ativos_str,kpi_incidentes_abertos_sem_atendente=kpi_incidentes_abertos_sem_atendente,kpi_incidentes_tempo_medio_atend_fechados_str=kpi_incidentes_tempo_medio_atend_fechados_str,pizza_incidentes_oracle_status_html=pizza_incidentes_oracle_status_html,kpi_total_nao_incidentes_criados=kpi_total_nao_incidentes_criados,kpi_nao_incidentes_fechados=kpi_nao_incidentes_fechados,kpi_nao_incidentes_em_atendimento=kpi_nao_incidentes_em_atendimento,kpi_nao_incidentes_aguard_solic=kpi_nao_incidentes_aguard_solic,kpi_nao_incidentes_contestados=kpi_nao_incidentes_contestados,kpi_nao_incidentes_aguard_aval_grupo=kpi_nao_incidentes_aguard_aval_grupo,kpi_nao_incidentes_aging_medio_ativos_str=kpi_nao_incidentes_aging_medio_ativos_str,kpi_nao_incidentes_abertos_sem_atendente=kpi_nao_incidentes_abertos_sem_atendente,kpi_nao_incidentes_tempo_medio_atend_str=kpi_nao_incidentes_tempo_medio_atend_str,pizza_nao_incidentes_oracle_status_html=pizza_nao_incidentes_oracle_status_html,data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),endpoint='dashboard_tv_oracle')

# --- ROTA DASHBOARD TV FORNECEDORES ---
@app.route('/dashboard_tv_fornecedores')
def dashboard_tv_fornecedores():
    print("--- ROTA /dashboard_tv_fornecedores: INÍCIO (Histórico, Foco Não Fechados) ---")
    
    hoje = date.today()
    data_inicio_str = date(2000, 1, 1).strftime('%Y-%m-%d')
    data_fim_str = hoje.strftime('%Y-%m-%d')
    
    print(f"Período de busca para TV Fornecedores (Histórico): {data_inicio_str} a {data_fim_str}")
    
    todos_chamados_historico_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)
    print(f"1. TV Fornecedores - Total chamados (histórico): {len(todos_chamados_historico_df)}")

    kpi_keys_fornecedores = ['total_em_aberto', 'em_atendimento', 'aguardando_solicitante', 'contestado', 'sla_estourado', 'abertos_7_dias_mais']
    dados_seven_incidentes = {key: 0 for key in kpi_keys_fornecedores}; dados_seven_incidentes['pizza_html'] = None
    dados_seven_outros = {key: 0 for key in kpi_keys_fornecedores}; dados_seven_outros['pizza_html'] = None
    dados_mmbit_incidentes = {key: 0 for key in kpi_keys_fornecedores}; dados_mmbit_incidentes['pizza_html'] = None
    dados_mmbit_outros = {key: 0 for key in kpi_keys_fornecedores}; dados_mmbit_outros['pizza_html'] = None
    primeiro_grafico_renderizado_fornecedores = False

    status_total_em_aberto_lista = STATUS_EM_ATENDIMENTO_LISTA + [STATUS_AGUARDANDO_SOLICITANTE, STATUS_CONTESTADO]

    if not todos_chamados_historico_df.empty and \
       all(col in todos_chamados_historico_df.columns for col in ['SERVICO', 'GRUPO', 'TIPOCHAMADO', 'STATUS', 'DT_ABERTURA_RAW', 'HORA_ABERTURA_RAW', 'PRAZO_HORAS', 'sla_atendimento_tempo_decorrido', 'sla_atendimento_tempo_definido']):

        seven_oracle_df = todos_chamados_historico_df[(todos_chamados_historico_df['SERVICO'] == SERVICO_ORACLE) & (todos_chamados_historico_df['GRUPO'] == GRUPO_SUSTENTACAO_SEVEN)].copy()
        if not seven_oracle_df.empty:
            seven_incidentes_df = seven_oracle_df[seven_oracle_df['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(seven_incidentes_df, None, plotly_js_config='cdn' if not primeiro_grafico_renderizado_fornecedores else False) # CHAMADA CORRETA
            dados_seven_incidentes = {**kpis, 'pizza_html': pizza_html}
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True

            seven_outros_df = seven_oracle_df[seven_oracle_df['TIPOCHAMADO'] != TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(seven_outros_df, None, plotly_js_config=not primeiro_grafico_renderizado_fornecedores) # CHAMADA CORRETA
            dados_seven_outros = {**kpis, 'pizza_html': pizza_html}
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True
        
        mmbit_geral_df = todos_chamados_historico_df[todos_chamados_historico_df['GRUPO'] == GRUPO_SUSTENTACAO_MMBIT].copy()
        if not mmbit_geral_df.empty:
            mmbit_incidentes_df = mmbit_geral_df[mmbit_geral_df['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(mmbit_incidentes_df, None, plotly_js_config=not primeiro_grafico_renderizado_fornecedores) # CHAMADA CORRETA
            dados_mmbit_incidentes = {**kpis, 'pizza_html': pizza_html}
            if pizza_html and not primeiro_grafico_renderizado_fornecedores: primeiro_grafico_renderizado_fornecedores = True

            mmbit_outros_df = mmbit_geral_df[mmbit_geral_df['TIPOCHAMADO'] != TIPO_CHAMADO_INCIDENTE].copy()
            kpis, pizza_html = gerar_kpis_e_pizza(mmbit_outros_df, None, plotly_js_config=not primeiro_grafico_renderizado_fornecedores) # CHAMADA CORRETA
            dados_mmbit_outros = {**kpis, 'pizza_html': pizza_html}
    else:
        print("ALERTA TV Fornecedores: DataFrame histórico vazio ou faltam colunas essenciais.")
        
    return render_template('dashboard_tv_fornecedores.html',
                           data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                           dados_seven_incidentes=dados_seven_incidentes,
                           dados_seven_outros=dados_seven_outros,
                           dados_mmbit_incidentes=dados_mmbit_incidentes,
                           dados_mmbit_outros=dados_mmbit_outros,
                           GRUPO_SUSTENTACAO_SEVEN_NOME=GRUPO_SUSTENTACAO_SEVEN,
                           GRUPO_SUSTENTACAO_MMBIT_NOME=GRUPO_SUSTENTACAO_MMBIT,
                           STATUS_TOTAL_EM_ABERTO_LISTA=status_total_em_aberto_lista,
                           data_inicio_link=data_inicio_str, 
                           data_fim_link=data_fim_str,
                           STATUS_EM_ATENDIMENTO_LISTA_PARA_LINK=STATUS_EM_ATENDIMENTO_LISTA,
                           STATUS_AGUARDANDO_SOLICITANTE_STR=STATUS_AGUARDANDO_SOLICITANTE,
                           STATUS_CONTESTADO_STR=STATUS_CONTESTADO,
                           endpoint='dashboard_tv_fornecedores'
                           )


# app.py
# ... (MANTENHA SUAS IMPORTAÇÕES E CONSTANTES GLOBAIS COMO ESTÃO NO SEU ARQUIVO) ...
# LISTA_GRUPOS_DBP também deve estar definida globalmente.

# --- ROTA DASHBOARD TV GERENCIAL (VERSÃO COMPLETA E CORRIGIDA) ---
@app.route('/dashboard_tv_gerencial')
def dashboard_tv_gerencial():
    print("--- ROTA /dashboard_tv_gerencial: INÍCIO ---")
    
    hoje = date.today()
    
    # --- Períodos de Data (Definidos no início) ---
    data_inicio_historico_str = date(2000, 1, 1).strftime('%Y-%m-%d') 
    data_fim_historico_str = hoje.strftime('%Y-%m-%d')
    data_inicio_12m_dt_obj = (pd.Timestamp(hoje) - pd.DateOffset(months=11)).replace(day=1).date()
    data_inicio_ultimos_7d_dt_obj = hoje - timedelta(days=6)
    data_inicio_ultimos_7d_link_str = data_inicio_ultimos_7d_dt_obj.strftime('%Y-%m-%d')
    data_fim_ultimos_7d_link_str = hoje.strftime('%Y-%m-%d')
    
    # --- Busca de Dados ---
    # Busca UMA VEZ para todo o histórico, cobrindo todos os KPIs e gráficos
    df_historico_geral = get_chamados(
        data_inicio=data_inicio_historico_str,
        data_fim=data_fim_historico_str,
        area_id=1 
    )
    print(f"1. TV Gerencial - Total chamados (todos os serviços, histórico): {len(df_historico_geral)}")

    # --- Inicializar Variáveis ---
    # KPIs Gerais (Serviço Oracle)
    kpis_gerais_oracle = {
        'em_atendimento': 0, 'aguardando_solicitante': 0, 'aguardando_avaliacao_grupo': 0,
        'contestados': 0, 'abertos_sem_atendente': 0, 'criados_ativos_ultimos_7_dias': 0,
        'aging_medio_ativos_str': "N/A", 'tempo_medio_atend_geral_str': "N/A"
    }
    # KPIs para Grupos DBP (Todos os Serviços)
    kpis_grupos_dbp = {nome_grupo: {'em_atendimento': 0, 'aguardando_solicitante': 0, 'contestado': 0, 'aberto_sem_atendente': 0} for nome_grupo in LISTA_GRUPOS_DBP}
    # Gráficos de Linha (Serviço Oracle)
    incidentes_12m_graph_html = None
    reqserv_12m_graph_html = None
    primeiro_grafico_plotly_renderizado = False

    # --- Início dos Cálculos ---
    if not df_historico_geral.empty:
        cols_base_necessarias = ['STATUS', 'GRUPO', 'DT_ABERTURA_RAW', 'HORA_ABERTURA_RAW', 'ATENDENTE', 'TIPOCHAMADO', 'SERVICO']
        coluna_tempo_usada_para_media = 'TEMPO_RESOLUCAO_DECORRIDO' 

        if all(col in df_historico_geral.columns for col in cols_base_necessarias) and \
           coluna_tempo_usada_para_media in df_historico_geral.columns:

            # 1. Calcular KPIs dos Grupos DBP (baseado em TODOS os serviços)
            df_ativos_geral = df_historico_geral[~df_historico_geral['STATUS'].isin(STATUS_FECHADO_LISTA) & (df_historico_geral['STATUS'] != STATUS_REPROVADO)].copy()
            if not df_ativos_geral.empty:
                for nome_grupo in LISTA_GRUPOS_DBP:
                    df_grupo_especifico = df_ativos_geral[df_ativos_geral['GRUPO'] == nome_grupo]
                    kpis_grupos_dbp[nome_grupo]['em_atendimento'] = len(df_grupo_especifico[df_grupo_especifico['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)])
                    kpis_grupos_dbp[nome_grupo]['aguardando_solicitante'] = len(df_grupo_especifico[df_grupo_especifico['STATUS'] == STATUS_AGUARDANDO_SOLICITANTE])
                    kpis_grupos_dbp[nome_grupo]['contestado'] = len(df_grupo_especifico[df_grupo_especifico['STATUS'] == STATUS_CONTESTADO])
                    kpis_grupos_dbp[nome_grupo]['aberto_sem_atendente'] = len(df_grupo_especifico[df_grupo_especifico['ATENDENTE'].isna() | (df_grupo_especifico['ATENDENTE'] == '')])
            
            # 2. Calcular KPIs Gerais e Gráficos do Serviço Oracle
            df_oracle_historico = df_historico_geral[df_historico_geral['SERVICO'] == SERVICO_ORACLE].copy()
            print(f"  Chamados Oracle para KPIs e Gráficos: {len(df_oracle_historico)}")
            if not df_oracle_historico.empty:
                df_oracle_ativos = df_oracle_historico[~df_oracle_historico['STATUS'].isin(STATUS_FECHADO_LISTA) & (df_oracle_historico['STATUS'] != STATUS_REPROVADO)].copy()
                if not df_oracle_ativos.empty:
                    kpis_gerais_oracle['em_atendimento'] = len(df_oracle_ativos[df_oracle_ativos['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA)])
                    kpis_gerais_oracle['aguardando_solicitante'] = len(df_oracle_ativos[df_oracle_ativos['STATUS'] == STATUS_AGUARDANDO_SOLICITANTE])
                    kpis_gerais_oracle['contestados'] = len(df_oracle_ativos[df_oracle_ativos['STATUS'] == STATUS_CONTESTADO])
                    df_aguard_aval = df_oracle_ativos[(df_oracle_ativos['GRUPO'] == GRUPO_AGUARDANDO_AVALIACAO) & (df_oracle_ativos['STATUS'].isin(STATUS_EM_ATENDIMENTO_LISTA + [STATUS_AGUARDANDO_SOLICITANTE, STATUS_AGUARDANDO_APROVACAO, STATUS_CONTESTADO]))]
                    kpis_gerais_oracle['aguardando_avaliacao_grupo'] = len(df_aguard_aval)
                    kpis_gerais_oracle['abertos_sem_atendente'] = len(df_oracle_ativos[df_oracle_ativos['ATENDENTE'].isna() | (df_oracle_ativos['ATENDENTE'] == '')])
                    df_ativos_7d = df_oracle_ativos[pd.to_datetime(df_oracle_ativos['DT_ABERTURA_RAW']).dt.date >= data_inicio_ultimos_7d_dt_obj]
                    kpis_gerais_oracle['criados_ativos_ultimos_7_dias'] = len(df_ativos_7d)
                    temp_aging = df_oracle_ativos.copy(); temp_aging.loc[:, 'HORA_ABERTURA_TD_TEMP'] = pd.to_timedelta(temp_aging['HORA_ABERTURA_RAW'].astype(str), errors='coerce'); temp_aging.loc[:, 'TIMESTAMP_ABERTURA'] = pd.to_datetime(temp_aging['DT_ABERTURA_RAW']) + temp_aging['HORA_ABERTURA_TD_TEMP']; temp_aging.dropna(subset=['TIMESTAMP_ABERTURA'], inplace=True)
                    if not temp_aging.empty: agora_kpi = datetime.now(); temp_aging.loc[:, 'IDADE_CHAMADO_TD'] = agora_kpi - temp_aging['TIMESTAMP_ABERTURA']; media_idade_td = temp_aging['IDADE_CHAMADO_TD'].mean()
                    if pd.notna(media_idade_td): dias = media_idade_td.days; horas = media_idade_td.seconds // 3600; kpis_gerais_oracle['aging_medio_ativos_str'] = f"{dias}d {horas}h"

                df_oracle_fechados = df_oracle_historico[df_oracle_historico['STATUS'].isin(STATUS_FECHADO_LISTA) & df_oracle_historico[coluna_tempo_usada_para_media].notna()].copy()
                if not df_oracle_fechados.empty:
                    df_oracle_fechados.loc[:, 'TEMPO_RESOL_NUM'] = pd.to_numeric(df_oracle_fechados[coluna_tempo_usada_para_media], errors='coerce'); df_oracle_fechados.dropna(subset=['TEMPO_RESOL_NUM'], inplace=True)
                    if not df_oracle_fechados.empty: media_tempo_original = df_oracle_fechados['TEMPO_RESOL_NUM'].mean()
                    if pd.notna(media_tempo_original): total_minutos_int = int(round(media_tempo_original)); horas = total_minutos_int // 60; minutos = total_minutos_int % 60; kpis_gerais_oracle['tempo_medio_atend_geral_str'] = f"{horas:02d}:{minutos:02d}h"
                
                df_graficos_12m = df_oracle_historico[pd.to_datetime(df_oracle_historico['DT_ABERTURA_RAW']).dt.date >= data_inicio_12m_dt_obj].copy()
                if not df_graficos_12m.empty:
                    incidentes_12m_df = df_graficos_12m[df_graficos_12m['TIPOCHAMADO'] == TIPO_CHAMADO_INCIDENTE].copy()
                    if not incidentes_12m_df.empty:
                        incidentes_12m_df.loc[:, 'MES_ANO'] = pd.to_datetime(incidentes_12m_df['DT_ABERTURA_RAW']).dt.to_period('M'); incidentes_por_mes = incidentes_12m_df.groupby('MES_ANO').size().reset_index(name='Contagem').sort_values(by='MES_ANO'); incidentes_por_mes['MES_ANO'] = incidentes_por_mes['MES_ANO'].astype(str) 
                        fig_inc = px.line(incidentes_por_mes, x='MES_ANO', y='Contagem', markers=True, title='Incidentes Criados/Mês (Últimos 12 Meses)', labels={'MES_ANO': 'Mês/Ano', 'Contagem': 'Nº Incidentes'}); fig_inc.update_layout(margin=dict(l=40,r=20,t=40,b=20), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD', title_x=0.5, title_font_size=14, xaxis=dict(showgrid=True, gridcolor='#444444', linecolor='#555555'), yaxis=dict(showgrid=True, gridcolor='#444444', linecolor='#555555')); fig_inc.update_xaxes(type='category', tickangle=-45)
                        incidentes_12m_graph_html = fig_inc.to_html(full_html=False, include_plotlyjs='cdn'); primeiro_grafico_plotly_renderizado = True
                    reqserv_12m_df = df_graficos_12m[df_graficos_12m['TIPOCHAMADO'] == TIPO_CHAMADO_REQUISICAO_SERVICO].copy()
                    if not reqserv_12m_df.empty:
                        reqserv_12m_df.loc[:, 'MES_ANO'] = pd.to_datetime(reqserv_12m_df['DT_ABERTURA_RAW']).dt.to_period('M'); reqserv_por_mes = reqserv_12m_df.groupby('MES_ANO').size().reset_index(name='Contagem').sort_values(by='MES_ANO'); reqserv_por_mes['MES_ANO'] = reqserv_por_mes['MES_ANO'].astype(str)
                        if not reqserv_por_mes.empty:
                            fig_req = px.line(reqserv_por_mes, x='MES_ANO', y='Contagem', markers=True, title='Requisições Criadas/Mês (Últimos 12 Meses)', labels={'MES_ANO': 'Mês/Ano', 'Contagem': 'Nº Requisições'}); fig_req.update_layout(margin=dict(l=40,r=20,t=40,b=20), height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD', title_x=0.5, title_font_size=14, xaxis=dict(showgrid=True, gridcolor='#444444', linecolor='#555555'), yaxis=dict(showgrid=True, gridcolor='#444444', linecolor='#555555')); fig_req.update_xaxes(type='category', tickangle=-45)
                            reqserv_12m_graph_html = fig_req.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_plotly_renderizado)
        else:
            print("ALERTA TV Gerencial: DataFrame geral vazio ou faltam colunas essenciais.")
    else:
        print("ALERTA TV Gerencial: Nenhum chamado no período de data amplo inicial.")
    
    return render_template('dashboard_tv_gerencial.html',
                           servico_foco=SERVICO_ORACLE,
                           kpis_gerais_oracle=kpis_gerais_oracle,
                           incidentes_12m_graph_html=incidentes_12m_graph_html,
                           reqserv_12m_graph_html=reqserv_12m_graph_html,
                           kpis_grupos_dbp=kpis_grupos_dbp, 
                           LISTA_GRUPOS_DBP_PARA_TEMPLATE=LISTA_GRUPOS_DBP, 
                           data_inicio_link_historico=data_inicio_historico_str, 
                           data_fim_link_historico=data_fim_historico_str,
                           data_inicio_link_7_dias=data_inicio_ultimos_7d_link_str,
                           data_fim_link_7_dias=data_fim_ultimos_7d_link_str, 
                           STATUS_AGUARDANDO_SOLICITANTE_STR=STATUS_AGUARDANDO_SOLICITANTE,
                           STATUS_CONTESTADO_STR=STATUS_CONTESTADO,
                           STATUS_EM_ATENDIMENTO_ESPECIFICO_STR=STATUS_EM_ATENDIMENTO_ESPECIFICO, 
                           STATUS_ENCERRADO_STR=STATUS_ENCERRADO, 
                           GRUPO_AGUARDANDO_AVALIACAO_NOME=GRUPO_AGUARDANDO_AVALIACAO,
                           STATUS_EM_ATENDIMENTO_LISTA_PARA_LINK=STATUS_EM_ATENDIMENTO_LISTA,
                           data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                           endpoint='dashboard_tv_gerencial'
                           )

# --- ROTA EXPORTAR EXCEL ---
@app.route('/exportar_excel')
def exportar_excel():
    # ... (CÓDIGO COMPLETO DA SUA ROTA exportar_excel - como no seu último app.py) ...
    # Certifique-se que usa 'STATUS' para filtrar e na lista colunas_principais
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