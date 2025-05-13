# app.py
from flask import Flask, render_template, request, url_for
from data_handler import get_chamados, get_distinct_servicos, get_distinct_tipos_chamado
from datetime import date, timedelta
import pandas as pd
import math
import plotly.express as px

app = Flask(__name__)

ITEMS_PER_PAGE = 50
TOP_N_DEPARTAMENTOS = 10 # Quantos principais departamentos mostrar

@app.route('/')
def index():
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

    print(f"Filtros: Início: {data_inicio_str}, Fim: {data_fim_str}, Página: {page}")
    
    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)

    total_chamados_filtrados = 0
    chamados_pagina_df = pd.DataFrame()
    total_pages = 0
    status_graph_html = None
    dept_graph_html = None # Inicializa o HTML do novo gráfico

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
        
        # --- Lógica para o Gráfico de Status ---
        if 'STATUS_CHAMADO' in todos_chamados_df.columns:
            status_counts = todos_chamados_df['STATUS_CHAMADO'].value_counts()
            if not status_counts.empty:
                fig_status = px.pie(
                    status_counts, 
                    names=status_counts.index, 
                    values=status_counts.values, 
                    title='Distribuição de Chamados por Status',
                    color_discrete_map={'ABERTO': 'orange', 'FECHADO': 'green'}
                )
                fig_status.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=350) # Reduzi um pouco a altura
                status_graph_html = fig_status.to_html(full_html=False, include_plotlyjs='cdn') # O primeiro gráfico carrega o JS
        
        # --- Lógica para o Gráfico de Departamentos (Top N) ---
        if 'DEPARTAMENTO' in todos_chamados_df.columns:
            # Contar chamados por departamento e pegar os TOP_N_DEPARTAMENTOS
            dept_counts = todos_chamados_df['DEPARTAMENTO'].value_counts().nlargest(TOP_N_DEPARTAMENTOS)
            if not dept_counts.empty:
                fig_dept = px.bar(
                    dept_counts,
                    x=dept_counts.index,
                    y=dept_counts.values,
                    title=f'Top {TOP_N_DEPARTAMENTOS} Departamentos por Nº de Chamados',
                    labels={'y': 'Nº de Chamados', 'index': 'Departamento'},
                    text=dept_counts.values # Mostra os valores nas barras
                )
                fig_dept.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=400)
                fig_dept.update_xaxes(tickangle=-45) # Inclina os nomes dos departamentos se forem longos
                # Para gráficos subsequentes na mesma página, não precisamos carregar o JS do Plotly novamente
                dept_graph_html = fig_dept.to_html(full_html=False, include_plotlyjs=False) 
                                                # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                # include_plotlyjs=False aqui!

    print(f"Total de chamados filtrados: {total_chamados_filtrados}, Exibindo página {page} de {total_pages}")

    return render_template('index.html',
                           chamados=chamados_pagina_df,
                           data_inicio=data_inicio_str,
                           data_fim=data_fim_str,
                           total_chamados=total_chamados_filtrados,
                           page=page,
                           total_pages=total_pages,
                           items_per_page=ITEMS_PER_PAGE,
                           status_graph_html=status_graph_html,
                           dept_graph_html=dept_graph_html) # Passa o HTML do novo gráfico

@app.route('/analise_detalhada')
def analise_detalhada():
    print("Acessando rota /analise_detalhada") # Para depuração

    # Obter parâmetros da URL
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')
    servico_selecionado = request.args.get('servico', '') # Padrão vazio se não selecionado
    tipo_chamado_selecionado = request.args.get('tipo_chamado', '') # Padrão vazio
    page = request.args.get('page', 1, type=int)

    # Definir datas padrão se não fornecidas
    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        data_fim_dt = date.today()
        data_inicio_dt = data_fim_dt - timedelta(days=29)
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
        data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    # Buscar dados para os filtros dropdown
    lista_servicos_df = get_distinct_servicos()
    lista_tipos_chamado_df = get_distinct_tipos_chamado()

    # Buscar todos os chamados com base no filtro de data inicial
    # (Os filtros de serviço e tipo serão aplicados no Pandas por enquanto)
    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)
    
    # Aplicar filtros de Serviço e Tipo de Chamado no DataFrame (se selecionados)
    chamados_filtrados_df = todos_chamados_df.copy() # Começa com todos os dados do período
    if servico_selecionado and not lista_servicos_df.empty:
        # Precisamos do nome do serviço, não do ID, para filtrar no DataFrame atual
        # Se tivéssemos o cd_servico no todos_chamados_df, poderíamos filtrar por ele.
        # Por ora, vamos assumir que a coluna 'SERVICO' (texto) existe no todos_chamados_df
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['SERVICO'] == servico_selecionado]
    
    if tipo_chamado_selecionado and not lista_tipos_chamado_df.empty:
        # Similarmente, para tipo de chamado, usando a coluna de descrição.
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['TIPOCHAMADO'] == tipo_chamado_selecionado]


    # Lógica de Paginação (similar à da página index)
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
    
    # TODO: Adicionar lógica para gráficos específicos desta página aqui

    return render_template('analise_detalhada.html',
                           chamados=chamados_pagina_df,
                           data_inicio=data_inicio_str,
                           data_fim=data_fim_str,
                           # Para os filtros
                           servicos=lista_servicos_df.to_dict(orient='records'),
                           tipos_chamado=lista_tipos_chamado_df.to_dict(orient='records'),
                           servico_selecionado=servico_selecionado,
                           tipo_chamado_selecionado=tipo_chamado_selecionado,
                           # Para paginação
                           total_chamados=total_chamados_final,
                           page=page,
                           total_pages=total_pages,
                           items_per_page=ITEMS_PER_PAGE
                           # Adicionar variáveis para gráficos aqui depois
                           )

if __name__ == '__main__':
    app.run(debug=True)