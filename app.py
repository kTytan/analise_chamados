# app.py
from flask import Flask, render_template, request, url_for, Response
from data_handler import (
    get_chamados, get_distinct_servicos, get_distinct_tipos_chamado,
    get_distinct_grupos_solucao, get_distinct_unidades
)
from datetime import date, timedelta, datetime # Adicionado datetime
import calendar
import pandas as pd
import math
import plotly.express as px
import io

app = Flask(__name__)

# Constantes Globais
ITEMS_PER_PAGE = 50
TOP_N_DEPARTAMENTOS = 10 # Usado na página index
TOP_N_GRUPOS = 10        # Usado na página analise_detalhada e TV
TOP_N_UNIDADES = 10      # Usado na página analise_detalhada e TV
TOP_N_SERVICOS = 10      # Usado na página analise_detalhada
TOP_N_DEPTOS_ORACLE_TV = 10 # Para o gráfico de barras na TV

# Nomes corretos para os grupos de solução para a TV
GRUPO_SUSTENTACAO_SEVEN = "Sustentação - SEVEN"
GRUPO_AGUARDANDO_AVALIACAO = "Aguardando Avaliação"
PRIORIDADES_CRITICAS_ALTAS = ['Crítica', 'Alta', 'Média', 'Baixa']

@app.route('/')
def index():
    print("Acessando rota / (index)")
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')
    page = request.args.get('page', 1, type=int)

    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        data_fim_dt = date.today() 
        data_inicio_dt = data_fim_dt - timedelta(days=29) 
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
        data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)

    total_chamados_filtrados = 0
    chamados_pagina_df = pd.DataFrame()
    total_pages = 0
    status_graph_html = None
    dept_graph_html = None
    primeiro_grafico_js_carregado_index = False


    if not todos_chamados_df.empty:
        total_chamados_filtrados = len(todos_chamados_df)
        total_pages = math.ceil(total_chamados_filtrados / ITEMS_PER_PAGE)

        if page < 1: page = 1
        elif page > total_pages and total_pages > 0: page = total_pages
        
        start_index = (page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        chamados_pagina_df = todos_chamados_df.iloc[start_index:end_index].copy()

        if 'DT_ABERTURA_RAW' in chamados_pagina_df.columns:
            chamados_pagina_df.loc[:, 'DT_ABERTURA_FORMATADA'] = chamados_pagina_df['DT_ABERTURA_RAW'].apply(
                lambda x: x.strftime('%d-%m-%Y') if pd.notna(x) else ''
            )

        if 'STATUS_CHAMADO' in todos_chamados_df.columns:
            status_counts = todos_chamados_df['STATUS_CHAMADO'].value_counts()
            if not status_counts.empty:
                fig_status = px.pie(status_counts, names=status_counts.index, values=status_counts.values, title='Distribuição de Chamados por Status', color_discrete_map={'ABERTO': 'orange', 'FECHADO': 'green'})
                fig_status.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=350) # Você pode adicionar o tema escuro aqui também se quiser
                status_graph_html = fig_status.to_html(full_html=False, include_plotlyjs='cdn')
                primeiro_grafico_js_carregado_index = True
        
        if 'DEPARTAMENTO' in todos_chamados_df.columns:
            dept_counts = todos_chamados_df['DEPARTAMENTO'].value_counts().nlargest(TOP_N_DEPARTAMENTOS)
            if not dept_counts.empty:
                fig_dept = px.bar(dept_counts, x=dept_counts.index, y=dept_counts.values, title=f'Top {TOP_N_DEPARTAMENTOS} Departamentos', labels={'y': 'Nº de Chamados', 'index': 'Departamento'}, text=dept_counts.values)
                fig_dept.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=400) # Você pode adicionar o tema escuro aqui também se quiser
                fig_dept.update_xaxes(tickangle=-45)
                dept_graph_html = fig_dept.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_index)

    return render_template('index.html',
                           chamados=chamados_pagina_df,
                           data_inicio=data_inicio_str, data_fim=data_fim_str,
                           total_chamados=total_chamados_filtrados,
                           page=page, total_pages=total_pages, items_per_page=ITEMS_PER_PAGE,
                           status_graph_html=status_graph_html,
                           dept_graph_html=dept_graph_html,
                           endpoint='index')


@app.route('/analise_detalhada')
def analise_detalhada():
    print("Acessando rota /analise_detalhada")
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')
    servico_selecionado_filtro = request.args.get('servico', '')
    tipo_chamado_selecionado_filtro = request.args.get('tipo_chamado', '')
    grupo_solucao_selecionado = request.args.get('grupo_solucao', '')
    unidade_selecionada = request.args.get('unidade', '')
    status_chamado_selecionado = request.args.get('status_chamado', '')
    page = request.args.get('page', 1, type=int)

    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        data_fim_dt = date.today()
        data_inicio_dt = data_fim_dt - timedelta(days=365 + 30) # Aprox. 13 meses para evolução
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
        data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    lista_servicos_df = get_distinct_servicos()
    lista_tipos_chamado_df = get_distinct_tipos_chamado()
    lista_grupos_solucao_df = get_distinct_grupos_solucao()
    lista_unidades_df = get_distinct_unidades()
    lista_status_chamado = ['ABERTO', 'FECHADO']

    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)
    
    chamados_filtrados_df = todos_chamados_df.copy()
    if servico_selecionado_filtro and 'SERVICO' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['SERVICO'] == servico_selecionado_filtro]
    if tipo_chamado_selecionado_filtro and 'TIPOCHAMADO' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['TIPOCHAMADO'] == tipo_chamado_selecionado_filtro]
    if grupo_solucao_selecionado and 'GRUPO' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['GRUPO'] == grupo_solucao_selecionado]
    if unidade_selecionada and 'UNIDADE' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['UNIDADE'] == unidade_selecionada]
    if status_chamado_selecionado and 'STATUS_CHAMADO' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['STATUS_CHAMADO'] == status_chamado_selecionado]

    grupo_graph_html = None
    unidade_graph_html = None
    servico_graph_html = None
    tipo_chamado_graph_html = None
    evolucao_mensal_geral_graph_html = None
    evolucao_tipo_graph_html = None
    primeiro_grafico_js_carregado_analise = False

    total_chamados_final = 0
    chamados_pagina_df = pd.DataFrame()
    total_pages = 0

    if not chamados_filtrados_df.empty:
        total_chamados_final = len(chamados_filtrados_df)
        total_pages = math.ceil(total_chamados_final / ITEMS_PER_PAGE)
        
        if page < 1: page = 1
        elif page > total_pages and total_pages > 0: page = total_pages
        
        start_index = (page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        chamados_pagina_df = chamados_filtrados_df.iloc[start_index:end_index].copy()

        if 'DT_ABERTURA_RAW' in chamados_pagina_df.columns:
            chamados_pagina_df.loc[:, 'DT_ABERTURA_FORMATADA'] = chamados_pagina_df['DT_ABERTURA_RAW'].apply(
                lambda x: x.strftime('%d-%m-%Y') if pd.notna(x) else ''
            )

        if 'GRUPO' in chamados_filtrados_df.columns:
            grupo_counts = chamados_filtrados_df['GRUPO'].value_counts().nlargest(TOP_N_GRUPOS)
            if not grupo_counts.empty:
                fig_grupo = px.bar(grupo_counts, x=grupo_counts.index, y=grupo_counts.values, title=f'Top {TOP_N_GRUPOS} Grupos de Solução', labels={'y': 'Nº de Chamados', 'index': 'Grupo'}, text=grupo_counts.values)
                fig_grupo.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=400)
                fig_grupo.update_xaxes(tickangle=-45)
                grupo_graph_html = fig_grupo.to_html(full_html=False, include_plotlyjs='cdn')
                primeiro_grafico_js_carregado_analise = True

        if 'UNIDADE' in chamados_filtrados_df.columns:
            unidade_counts = chamados_filtrados_df['UNIDADE'].value_counts().nlargest(TOP_N_UNIDADES)
            if not unidade_counts.empty:
                fig_unidade = px.bar(unidade_counts, x=unidade_counts.index, y=unidade_counts.values, title=f'Top {TOP_N_UNIDADES} Unidades', labels={'y': 'Nº de Chamados', 'index': 'Unidade'}, text=unidade_counts.values)
                fig_unidade.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=400)
                fig_unidade.update_xaxes(tickangle=-45)
                unidade_graph_html = fig_unidade.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_analise)
                if not primeiro_grafico_js_carregado_analise: primeiro_grafico_js_carregado_analise = True
        
        if 'SERVICO' in chamados_filtrados_df.columns:
            servico_counts = chamados_filtrados_df['SERVICO'].value_counts().nlargest(TOP_N_SERVICOS)
            if not servico_counts.empty:
                fig_servico = px.bar(servico_counts, x=servico_counts.index, y=servico_counts.values, title=f'Top {TOP_N_SERVICOS} Serviços', labels={'y': 'Nº de Chamados', 'index': 'Serviço'}, text=servico_counts.values)
                fig_servico.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=400)
                fig_servico.update_xaxes(tickangle=-45)
                servico_graph_html = fig_servico.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_analise)
                if not primeiro_grafico_js_carregado_analise: primeiro_grafico_js_carregado_analise = True

        if 'TIPOCHAMADO' in chamados_filtrados_df.columns:
            tipo_chamado_counts = chamados_filtrados_df['TIPOCHAMADO'].value_counts()
            if not tipo_chamado_counts.empty:
                fig_tipo_chamado = px.pie(tipo_chamado_counts, names=tipo_chamado_counts.index, values=tipo_chamado_counts.values, title='Distribuição por Tipo de Chamado')
                fig_tipo_chamado.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=350)
                tipo_chamado_graph_html = fig_tipo_chamado.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_analise)
                if not primeiro_grafico_js_carregado_analise: primeiro_grafico_js_carregado_analise = True
        
        if 'DT_ABERTURA_RAW' in chamados_filtrados_df.columns:
            df_evol_geral = chamados_filtrados_df.copy()
            df_evol_geral['DT_ABERTURA_RAW'] = pd.to_datetime(df_evol_geral['DT_ABERTURA_RAW'], errors='coerce')
            df_evol_geral.dropna(subset=['DT_ABERTURA_RAW'], inplace=True)
            if not df_evol_geral.empty:
                df_evol_geral['MES_ANO_ABERTURA'] = df_evol_geral['DT_ABERTURA_RAW'].dt.to_period('M')
                chamados_por_mes_geral = df_evol_geral.groupby('MES_ANO_ABERTURA').size().reset_index(name='CONTAGEM').sort_values(by='MES_ANO_ABERTURA')
                chamados_por_mes_geral['MES_ANO_ABERTURA'] = chamados_por_mes_geral['MES_ANO_ABERTURA'].astype(str)
                if not chamados_por_mes_geral.empty:
                    fig_evol_geral = px.line(chamados_por_mes_geral, x='MES_ANO_ABERTURA', y='CONTAGEM', title='Evolução Mensal Geral de Chamados', markers=True, labels={'MES_ANO_ABERTURA': 'Mês/Ano', 'CONTAGEM': 'Nº de Chamados'})
                    fig_evol_geral.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=450)
                    fig_evol_geral.update_xaxes(tickangle=-45, type='category')
                    evolucao_mensal_geral_graph_html = fig_evol_geral.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_analise)
                    if not primeiro_grafico_js_carregado_analise: primeiro_grafico_js_carregado_analise = True

        if 'DT_ABERTURA_RAW' in chamados_filtrados_df.columns and 'TIPOCHAMADO' in chamados_filtrados_df.columns:
            df_evol_tipo = chamados_filtrados_df.copy()
            df_evol_tipo['DT_ABERTURA_RAW'] = pd.to_datetime(df_evol_tipo['DT_ABERTURA_RAW'], errors='coerce')
            df_evol_tipo.dropna(subset=['DT_ABERTURA_RAW', 'TIPOCHAMADO'], inplace=True)
            if not df_evol_tipo.empty:
                df_evol_tipo['MES_ANO_ABERTURA'] = df_evol_tipo['DT_ABERTURA_RAW'].dt.to_period('M')
                chamados_por_mes_tipo = df_evol_tipo.groupby(['MES_ANO_ABERTURA', 'TIPOCHAMADO']).size().reset_index(name='CONTAGEM').sort_values(by=['MES_ANO_ABERTURA', 'TIPOCHAMADO'])
                chamados_por_mes_tipo['MES_ANO_ABERTURA'] = chamados_por_mes_tipo['MES_ANO_ABERTURA'].astype(str)
                if not chamados_por_mes_tipo.empty:
                    fig_evolucao_tipo = px.line(chamados_por_mes_tipo,x='MES_ANO_ABERTURA',y='CONTAGEM',color='TIPOCHAMADO',title='Evolução Mensal de Chamados por Tipo',markers=True,labels={'MES_ANO_ABERTURA': 'Mês/Ano', 'CONTAGEM': 'Nº de Chamados', 'TIPOCHAMADO': 'Tipo'})
                    fig_evolucao_tipo.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=450)
                    fig_evolucao_tipo.update_xaxes(tickangle=-45, type='category')
                    evolucao_tipo_graph_html = fig_evolucao_tipo.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_analise)

    return render_template('analise_detalhada.html',
                           chamados=chamados_pagina_df,
                           data_inicio=data_inicio_str, data_fim=data_fim_str,
                           servicos=lista_servicos_df.to_dict(orient='records'),
                           tipos_chamado=lista_tipos_chamado_df.to_dict(orient='records'),
                           grupos_solucao=lista_grupos_solucao_df.to_dict(orient='records'),
                           unidades=lista_unidades_df.to_dict(orient='records'),
                           lista_status_chamado=lista_status_chamado,
                           servico_selecionado=servico_selecionado_filtro,
                           tipo_chamado_selecionado=tipo_chamado_selecionado_filtro,
                           grupo_solucao_selecionado=grupo_solucao_selecionado,
                           unidade_selecionada=unidade_selecionada,
                           status_chamado_selecionado=status_chamado_selecionado,
                           total_chamados=total_chamados_final,
                           page=page, total_pages=total_pages, items_per_page=ITEMS_PER_PAGE,
                           grupo_graph_html=grupo_graph_html,
                           unidade_graph_html=unidade_graph_html,
                           servico_graph_html=servico_graph_html,
                           tipo_chamado_graph_html=tipo_chamado_graph_html,
                           evolucao_mensal_geral_graph_html=evolucao_mensal_geral_graph_html,
                           evolucao_tipo_graph_html=evolucao_tipo_graph_html,
                           endpoint='analise_detalhada'
                           )

@app.route('/dashboard_tv_oracle')
def dashboard_tv_oracle():
    print("--- ROTA /dashboard_tv_oracle: INÍCIO (Dados do Mês Atual) ---")
    servico_filtro_oracle = "1-SISTEMAS (ERP Oracle)"

    hoje = date.today() 
    primeiro_dia_mes_atual = hoje.replace(day=1)
    dias_no_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    ultimo_dia_mes_atual = hoje.replace(day=dias_no_mes)

    data_inicio_str = primeiro_dia_mes_atual.strftime('%Y-%m-%d')
    data_fim_str = ultimo_dia_mes_atual.strftime('%Y-%m-%d')
    
    print(f"Período de busca para TV Dashboard (Mês Atual): {data_inicio_str} a {data_fim_str}")

    todos_chamados_mes_atual_df = get_chamados(
        data_inicio=data_inicio_str,
        data_fim=data_fim_str,
        area_id=1
    )
    print(f"1. Total de chamados buscados no mês atual: {len(todos_chamados_mes_atual_df)}")

    # Inicializar todas as variáveis de resultado
    total_incidentes_oracle_mes = 0
    abertos_incidentes_oracle_mes = 0
    fechados_incidentes_oracle_mes = 0
    pizza_geral_oracle_status_html = None
    total_incidentes_sust_seven_mes = 0
    abertos_incidentes_sust_seven_mes = 0
    fechados_incidentes_sust_seven_mes = 0
    pizza_sust_seven_status_html = None
    abertos_incidentes_aguardando_aval_mes = 0
    depto_abertos_oracle_graph_html = None
    
    # Novas variáveis
    abertos_incidentes_criticos_altos_oracle_mes = 0
    prioridade_abertos_oracle_graph_html = None
    
    primeiro_grafico_js_carregado_tv = False

    if not todos_chamados_mes_atual_df.empty:
        oracle_df_mes_atual = todos_chamados_mes_atual_df[
            todos_chamados_mes_atual_df['SERVICO'] == servico_filtro_oracle
        ].copy()
        print(f"2. Chamados Oracle no mês atual: {len(oracle_df_mes_atual)}")

        if not oracle_df_mes_atual.empty:
            oracle_incidentes_todos_status_mes_df = pd.DataFrame()
            if 'TIPOCHAMADO' in oracle_df_mes_atual.columns:
                oracle_incidentes_todos_status_mes_df = oracle_df_mes_atual[
                    oracle_df_mes_atual['TIPOCHAMADO'] == 'Incidente'
                ].copy()
            print(f"3. Incidentes Oracle (todos os status) criados no mês atual: {len(oracle_incidentes_todos_status_mes_df)}")

            if not oracle_incidentes_todos_status_mes_df.empty and 'STATUS_CHAMADO' in oracle_incidentes_todos_status_mes_df.columns:
                total_incidentes_oracle_mes = len(oracle_incidentes_todos_status_mes_df)
                abertos_incidentes_oracle_mes = len(oracle_incidentes_todos_status_mes_df[oracle_incidentes_todos_status_mes_df['STATUS_CHAMADO'] == 'ABERTO'])
                fechados_incidentes_oracle_mes = len(oracle_incidentes_todos_status_mes_df[oracle_incidentes_todos_status_mes_df['STATUS_CHAMADO'] == 'FECHADO'])
                
                status_counts_geral = oracle_incidentes_todos_status_mes_df['STATUS_CHAMADO'].value_counts()
                if not status_counts_geral.empty and status_counts_geral.sum() > 0 :
                    fig_pizza_geral = px.pie(status_counts_geral, names=status_counts_geral.index, values=status_counts_geral.values, 
                                             title='Status Incidentes Oracle (Mês)', hole=0.3,
                                             color_discrete_map={'ABERTO': 'orange', 'FECHADO': 'green'})
                    fig_pizza_geral.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=280,
                                                  paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD',
                                                  legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                    pizza_geral_oracle_status_html = fig_pizza_geral.to_html(full_html=False, include_plotlyjs='cdn')
                    primeiro_grafico_js_carregado_tv = True

                if 'GRUPO' in oracle_incidentes_todos_status_mes_df.columns:
                    df_sust_seven_todos_status = oracle_incidentes_todos_status_mes_df[
                        oracle_incidentes_todos_status_mes_df['GRUPO'] == GRUPO_SUSTENTACAO_SEVEN
                    ].copy()
                    if not df_sust_seven_todos_status.empty:
                        total_incidentes_sust_seven_mes = len(df_sust_seven_todos_status)
                        abertos_incidentes_sust_seven_mes = len(df_sust_seven_todos_status[df_sust_seven_todos_status['STATUS_CHAMADO'] == 'ABERTO'])
                        fechados_incidentes_sust_seven_mes = len(df_sust_seven_todos_status[df_sust_seven_todos_status['STATUS_CHAMADO'] == 'FECHADO'])
                        status_counts_sust_seven = df_sust_seven_todos_status['STATUS_CHAMADO'].value_counts()
                        if not status_counts_sust_seven.empty and status_counts_sust_seven.sum() > 0:
                            fig_pizza_sust_seven = px.pie(status_counts_sust_seven, names=status_counts_sust_seven.index, values=status_counts_sust_seven.values,
                                                          title=f'Status: {GRUPO_SUSTENTACAO_SEVEN} (Mês)', hole=0.3,
                                                          color_discrete_map={'ABERTO': 'orange', 'FECHADO': 'green'})
                            fig_pizza_sust_seven.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=280,
                                                               paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD',
                                                               legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                            pizza_sust_seven_status_html = fig_pizza_sust_seven.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_tv)
                            if not primeiro_grafico_js_carregado_tv: primeiro_grafico_js_carregado_tv = True
                
                # DataFrame base para os próximos KPIs/Gráficos que são apenas sobre ABERTOS
                oracle_incidentes_abertos_mes_df = oracle_incidentes_todos_status_mes_df[
                    oracle_incidentes_todos_status_mes_df['STATUS_CHAMADO'] == 'ABERTO'
                ].copy()
                print(f"4. DataFrame oracle_incidentes_abertos_mes_df (para KPIs restantes): {len(oracle_incidentes_abertos_mes_df)}")

                if not oracle_incidentes_abertos_mes_df.empty:
                    # KPI: Incidentes Oracle ABERTOS em "Aguardando Avaliação" (Mês Atual)
                    if 'GRUPO' in oracle_incidentes_abertos_mes_df.columns:
                        df_abertos_aguardando_aval = oracle_incidentes_abertos_mes_df[
                            oracle_incidentes_abertos_mes_df['GRUPO'] == GRUPO_AGUARDANDO_AVALIACAO
                        ]
                        abertos_incidentes_aguardando_aval_mes = len(df_abertos_aguardando_aval)
                        print(f"DEBUG: Contagem ABERTOS para '{GRUPO_AGUARDANDO_AVALIACAO}' (mês atual): {abertos_incidentes_aguardando_aval_mes}")

                    # NOVO KPI: Incidentes Críticos/Altos ABERTOS (Oracle, Mês Atual)
                    if 'PRIORIDADE' in oracle_incidentes_abertos_mes_df.columns:
                        criticos_altos_df = oracle_incidentes_abertos_mes_df[
                            oracle_incidentes_abertos_mes_df['PRIORIDADE'].isin(PRIORIDADES_CRITICAS_ALTAS)
                        ]
                        abertos_incidentes_criticos_altos_oracle_mes = len(criticos_altos_df)
                        print(f"DEBUG: Contagem ABERTOS Críticos/Altos (mês atual): {abertos_incidentes_criticos_altos_oracle_mes}")

                    # NOVO GRÁFICO: Incidentes Oracle ABERTOS por Prioridade (Mês Atual)
                    if 'PRIORIDADE' in oracle_incidentes_abertos_mes_df.columns:
                        prioridade_counts = oracle_incidentes_abertos_mes_df['PRIORIDADE'].value_counts()
                        if not prioridade_counts.empty:
                            fig_prioridade = px.bar(
                                prioridade_counts, x=prioridade_counts.index, y=prioridade_counts.values,
                                title='Incidentes Oracle Abertos por Prioridade (Mês)',
                                labels={'y': 'Nº de Incidentes', 'index': 'Prioridade'},
                                text=prioridade_counts.values,
                                color=prioridade_counts.index, # Opcional: cores por prioridade
                                color_discrete_map={ # Exemplo de cores, ajuste conforme suas prioridades
                                    'Crítica': 'red', 
                                    'Alta': 'orangered',
                                    'Média': 'orange',
                                    'Baixa': 'gold'
                                }
                            )
                            fig_prioridade.update_layout(margin=dict(l=40, r=20, t=60, b=20), height=400,
                                                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD')
                            fig_prioridade.update_xaxes(tickangle=-45)
                            prioridade_abertos_oracle_graph_html = fig_prioridade.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_tv)
                            if not primeiro_grafico_js_carregado_tv: primeiro_grafico_js_carregado_tv = True

                    # Gráfico: Incidentes Oracle ABERTOS (Mês Atual) por Departamento
                    if 'DEPARTAMENTO' in oracle_incidentes_abertos_mes_df.columns:
                        abertos_por_depto_counts = oracle_incidentes_abertos_mes_df['DEPARTAMENTO'].value_counts().nlargest(TOP_N_DEPTOS_ORACLE_TV)
                        if not abertos_por_depto_counts.empty:
                            fig_depto_abertos = px.bar(
                                abertos_por_depto_counts, x=abertos_por_depto_counts.index, y=abertos_por_depto_counts.values,
                                title=f'Top {TOP_N_DEPTOS_ORACLE_TV} Deptos com Incidentes Oracle Abertos (Mês Atual)',
                                labels={'y': 'Nº de Incidentes Abertos', 'index': 'Departamento'}, text=abertos_por_depto_counts.values
                            )
                            fig_depto_abertos.update_layout(margin=dict(l=40, r=20, t=60, b=20), height=450,
                                                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#DDDDDD')
                            fig_depto_abertos.update_xaxes(tickangle=-45)
                            depto_abertos_oracle_graph_html = fig_depto_abertos.to_html(full_html=False, include_plotlyjs=not primeiro_grafico_js_carregado_tv)
                            if not primeiro_grafico_js_carregado_tv: primeiro_grafico_js_carregado_tv = True
            else:
                print("ALERTA: DataFrame de Incidentes Oracle (mês atual) está vazio ou falta a coluna STATUS_CHAMADO para processamento detalhado.")
        else:
            print(f"Nenhum chamado encontrado para o serviço '{servico_filtro_oracle}' no mês atual.")
    else:
        print("DataFrame todos_chamados_mes_atual_df está vazio (nenhum chamado no mês atual).")
        
    # ... (print de valores finais e return render_template) ...
    print(f"Valores finais: TotOraMês={total_incidentes_oracle_mes}, AberOraMês={abertos_incidentes_oracle_mes}, FechOraMês={fechados_incidentes_oracle_mes}, "
          f"TotSust7Mês={total_incidentes_sust_seven_mes}, AberSust7Mês={abertos_incidentes_sust_seven_mes}, FechSust7Mês={fechados_incidentes_sust_seven_mes}, "
          f"AberAgAvalMês={abertos_incidentes_aguardando_aval_mes}, AberCritAltos={abertos_incidentes_criticos_altos_oracle_mes}")
    
    return render_template('dashboard_tv_oracle.html',
                           servico_foco=servico_filtro_oracle,
                           total_incidentes_oracle_mes=total_incidentes_oracle_mes,
                           abertos_incidentes_oracle_mes=abertos_incidentes_oracle_mes,
                           fechados_incidentes_oracle_mes=fechados_incidentes_oracle_mes,
                           pizza_geral_oracle_status_html=pizza_geral_oracle_status_html,
                           total_incidentes_sust_seven_mes=total_incidentes_sust_seven_mes,
                           abertos_incidentes_sust_seven_mes=abertos_incidentes_sust_seven_mes,
                           fechados_incidentes_sust_seven_mes=fechados_incidentes_sust_seven_mes,
                           pizza_sust_seven_status_html=pizza_sust_seven_status_html,
                           abertos_incidentes_aguardando_aval_mes=abertos_incidentes_aguardando_aval_mes,
                           abertos_incidentes_criticos_altos_oracle_mes=abertos_incidentes_criticos_altos_oracle_mes, # NOVO KPI
                           prioridade_abertos_oracle_graph_html=prioridade_abertos_oracle_graph_html, # NOVO GRÁFICO
                           depto_abertos_oracle_graph_html=depto_abertos_oracle_graph_html,
                           data_atualizacao=datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                           )


@app.route('/exportar_excel')
def exportar_excel():
    print("Acessando rota /exportar_excel")
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')
    servico_selecionado = request.args.get('servico', '')
    tipo_chamado_selecionado = request.args.get('tipo_chamado', '')
    grupo_solucao_selecionado = request.args.get('grupo_solucao', '') # Adicionado
    unidade_selecionada = request.args.get('unidade', '')             # Adicionado
    status_chamado_selecionado = request.args.get('status_chamado', '') # Adicionado
    area_id_param = request.args.get('area_id', 1, type=int)

    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        data_fim_dt = date.today()
        data_inicio_dt = data_fim_dt - timedelta(days=29)
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
        data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    print(f"Exportando para Excel com filtros - Início: {data_inicio_str}, Fim: {data_fim_str}, "
          f"Serviço: '{servico_selecionado}', Tipo: '{tipo_chamado_selecionado}', "
          f"Grupo: '{grupo_solucao_selecionado}', Unidade: '{unidade_selecionada}', "
          f"Status: '{status_chamado_selecionado}', Área: {area_id_param}")

    chamados_para_exportar_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=area_id_param)

    if servico_selecionado and 'SERVICO' in chamados_para_exportar_df.columns:
        chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['SERVICO'] == servico_selecionado]
    if tipo_chamado_selecionado and 'TIPOCHAMADO' in chamados_para_exportar_df.columns:
        chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['TIPOCHAMADO'] == tipo_chamado_selecionado]
    if grupo_solucao_selecionado and 'GRUPO' in chamados_para_exportar_df.columns:
        chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['GRUPO'] == grupo_solucao_selecionado]
    if unidade_selecionada and 'UNIDADE' in chamados_para_exportar_df.columns:
        chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['UNIDADE'] == unidade_selecionada]
    if status_chamado_selecionado and 'STATUS_CHAMADO' in chamados_para_exportar_df.columns:
        chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['STATUS_CHAMADO'] == status_chamado_selecionado]


    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        colunas_principais = [
            'CHAMADO', 'TITULO', 'SOLICITANTE', 'DEPARTAMENTO', 'UNIDADE', 
            'SERVICO', 'TEMA', 'TIPOCHAMADO', 'TEMPLATE', 'GRUPO', 
            'CATEGORIA', 'PRIORIDADE', 'ATENDENTE', 'DESCRICAO', 
            'PRAZO_HORAS', 'STATUS_CHAMADO'
        ]
        datas_horas_formatadas = {}
        df_export_temp = chamados_para_exportar_df.copy()

        for col_raw in [c for c in df_export_temp.columns if '_RAW' in c and 'DT_' in c]:
            col_format_name = col_raw.replace('_RAW', '').replace('DT_', 'DATA_') # ex DATA_ABERTURA
            if col_raw in df_export_temp.columns:
                datas_horas_formatadas[col_format_name] = pd.to_datetime(df_export_temp[col_raw], errors='coerce').dt.strftime('%d-%m-%Y')
        
        for col_raw in [c for c in df_export_temp.columns if '_RAW' in c and 'HORA_' in c]:
            col_format_name = col_raw.replace('_RAW', '') # ex HORA_ABERTURA
            if col_raw in df_export_temp.columns:
                datas_horas_formatadas[col_format_name] = df_export_temp[col_raw].astype(str).apply(lambda x: x.split()[-1] if ' ' in x else x) # Pega só a parte da hora se for timedelta

        df_export_final = df_export_temp[[col for col in colunas_principais if col in df_export_temp.columns]]
        for col_name, col_data in datas_horas_formatadas.items():
            df_export_final[col_name] = col_data
        
        df_export_final.to_excel(writer, index=False, sheet_name='Chamados')
        workbook  = writer.book
        worksheet = writer.sheets['Chamados']
        for i, col in enumerate(df_export_final.columns):
            column_len = df_export_final[col].astype(str).map(len).max()
            column_len = max(column_len, len(col)) if not pd.isna(column_len) else len(col)
            worksheet.set_column(i, i, min(column_len + 2, 50))
            
    excel_data = output.getvalue()
    filename = f"chamados_exportados_{date.today().strftime('%Y%m%d')}.xlsx" # Nome de arquivo mais genérico
    return Response(
        excel_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)