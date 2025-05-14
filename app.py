# app.py
from flask import Flask, render_template, request, url_for, Response
import io
from data_handler import (
    get_chamados, get_distinct_servicos, get_distinct_tipos_chamado,
    get_distinct_grupos_solucao, get_distinct_unidades
)
from datetime import date, timedelta
import pandas as pd
import math
import plotly.express as px

app = Flask(__name__)

ITEMS_PER_PAGE = 50
TOP_N_DEPARTAMENTOS = 10
TOP_N_GRUPOS = 10
TOP_N_UNIDADES = 10
TOP_N_SERVICOS = 10

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
                           endpoint='index',
                           chamados=chamados_pagina_df,
                           data_inicio=data_inicio_str,
                           data_fim=data_fim_str,
                           total_chamados=total_chamados_filtrados,
                           page=page,
                           total_pages=total_pages,
                           items_per_page=ITEMS_PER_PAGE,
                           status_graph_html=status_graph_html,
                           dept_graph_html=dept_graph_html
                           ) # Passa o HTML do novo gráfico

@app.route('/analise_detalhada')
def analise_detalhada():
    print("Acessando rota /analise_detalhada")

    # Obter parâmetros da URL
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')
    servico_selecionado_filtro = request.args.get('servico', '') # Renomeado para evitar conflito
    tipo_chamado_selecionado_filtro = request.args.get('tipo_chamado', '') # Renomeado
    grupo_solucao_selecionado = request.args.get('grupo_solucao', '')
    unidade_selecionada = request.args.get('unidade', '')
    page = request.args.get('page', 1, type=int)

    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        data_fim_dt = date.today() # Data atual: 14/05/2025 (Exemplo)
        data_inicio_dt = data_fim_dt - timedelta(days=29) # Últimos 30 dias
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
        data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    # Buscar dados para os filtros dropdown
    lista_servicos_df = get_distinct_servicos()
    lista_tipos_chamado_df = get_distinct_tipos_chamado()
    lista_grupos_solucao_df = get_distinct_grupos_solucao()
    lista_unidades_df = get_distinct_unidades()

    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)
    
    chamados_filtrados_df = todos_chamados_df.copy()
    # Aplicar filtros no DataFrame
    if servico_selecionado_filtro and 'SERVICO' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['SERVICO'] == servico_selecionado_filtro]
    if tipo_chamado_selecionado_filtro and 'TIPOCHAMADO' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['TIPOCHAMADO'] == tipo_chamado_selecionado_filtro]
    if grupo_solucao_selecionado and 'GRUPO' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['GRUPO'] == grupo_solucao_selecionado]
    if unidade_selecionada and 'UNIDADE' in chamados_filtrados_df.columns:
        chamados_filtrados_df = chamados_filtrados_df[chamados_filtrados_df['UNIDADE'] == unidade_selecionada]

    # Inicializar HTML dos gráficos
    grupo_graph_html = None
    unidade_graph_html = None
    servico_graph_html = None # Novo
    tipo_chamado_graph_html = None # Novo

    # Lógica de Paginação e Gráficos
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

        # --- Gráfico: Chamados por Grupo de Solução ---
        if 'GRUPO' in chamados_filtrados_df.columns:
            grupo_counts = chamados_filtrados_df['GRUPO'].value_counts().nlargest(TOP_N_GRUPOS)
            if not grupo_counts.empty:
                fig_grupo = px.bar(grupo_counts, x=grupo_counts.index, y=grupo_counts.values, title=f'Top {TOP_N_GRUPOS} Grupos de Solução', labels={'y': 'Nº de Chamados', 'index': 'Grupo'}, text=grupo_counts.values)
                fig_grupo.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=400)
                fig_grupo.update_xaxes(tickangle=-45)
                grupo_graph_html = fig_grupo.to_html(full_html=False, include_plotlyjs='cdn') # Primeiro gráfico carrega JS

        # --- Gráfico: Chamados por Unidade ---
        if 'UNIDADE' in chamados_filtrados_df.columns:
            unidade_counts = chamados_filtrados_df['UNIDADE'].value_counts().nlargest(TOP_N_UNIDADES)
            if not unidade_counts.empty:
                fig_unidade = px.bar(unidade_counts, x=unidade_counts.index, y=unidade_counts.values, title=f'Top {TOP_N_UNIDADES} Unidades', labels={'y': 'Nº de Chamados', 'index': 'Unidade'}, text=unidade_counts.values)
                fig_unidade.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=400)
                fig_unidade.update_xaxes(tickangle=-45)
                unidade_graph_html = fig_unidade.to_html(full_html=False, include_plotlyjs=False) # JS já carregado

        # --- Gráfico: Chamados por Serviço (Top N) ---
        if 'SERVICO' in chamados_filtrados_df.columns:
            servico_counts = chamados_filtrados_df['SERVICO'].value_counts().nlargest(TOP_N_SERVICOS)
            if not servico_counts.empty:
                fig_servico = px.bar(servico_counts, x=servico_counts.index, y=servico_counts.values, title=f'Top {TOP_N_SERVICOS} Serviços', labels={'y': 'Nº de Chamados', 'index': 'Serviço'}, text=servico_counts.values)
                fig_servico.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=400)
                fig_servico.update_xaxes(tickangle=-45)
                servico_graph_html = fig_servico.to_html(full_html=False, include_plotlyjs=False)

        # --- Gráfico: Chamados por Tipo de Chamado ---
        if 'TIPOCHAMADO' in chamados_filtrados_df.columns:
            tipo_chamado_counts = chamados_filtrados_df['TIPOCHAMADO'].value_counts()
            if not tipo_chamado_counts.empty:
                fig_tipo_chamado = px.pie(tipo_chamado_counts, names=tipo_chamado_counts.index, values=tipo_chamado_counts.values, title='Distribuição por Tipo de Chamado')
                fig_tipo_chamado.update_layout(margin=dict(l=20, r=20, t=50, b=20), height=350)
                tipo_chamado_graph_html = fig_tipo_chamado.to_html(full_html=False, include_plotlyjs=False)
                
    return render_template('analise_detalhada.html',
                           chamados=chamados_pagina_df,
                           data_inicio=data_inicio_str, data_fim=data_fim_str,
                           servicos=lista_servicos_df.to_dict(orient='records'),
                           tipos_chamado=lista_tipos_chamado_df.to_dict(orient='records'),
                           grupos_solucao=lista_grupos_solucao_df.to_dict(orient='records'),
                           unidades=lista_unidades_df.to_dict(orient='records'),
                           servico_selecionado=servico_selecionado_filtro, # Passando o valor do filtro
                           tipo_chamado_selecionado=tipo_chamado_selecionado_filtro, # Passando o valor do filtro
                           grupo_solucao_selecionado=grupo_solucao_selecionado,
                           unidade_selecionada=unidade_selecionada,
                           total_chamados=total_chamados_final,
                           page=page, total_pages=total_pages, items_per_page=ITEMS_PER_PAGE,
                           grupo_graph_html=grupo_graph_html,
                           unidade_graph_html=unidade_graph_html,
                           servico_graph_html=servico_graph_html,         # Novo
                           tipo_chamado_graph_html=tipo_chamado_graph_html,
                           endpoint='analise_detalhada' # Novo
                           )

@app.route('/exportar_excel')
def exportar_excel():
    print("Acessando rota /exportar_excel")

    # Obter parâmetros de filtro da URL
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')
    servico_selecionado = request.args.get('servico', '')
    tipo_chamado_selecionado = request.args.get('tipo_chamado', '')
    area_id_param = request.args.get('area_id', 1, type=int) # Pega area_id, padrão 1

    # Definir datas padrão se não fornecidas (similar às outras rotas)
    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        data_fim_dt = date.today()
        data_inicio_dt = data_fim_dt - timedelta(days=29)
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
        data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    print(f"Exportando para Excel com filtros - Início: {data_inicio_str}, Fim: {data_fim_str}, "
          f"Serviço: '{servico_selecionado}', Tipo: '{tipo_chamado_selecionado}', Área: {area_id_param}")

    # Buscar TODOS os chamados com base no filtro de data e área
    # A função get_chamados já lida com area_id
    chamados_para_exportar_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=area_id_param)

    # Aplicar filtros de Serviço e Tipo de Chamado no DataFrame (se selecionados)
    if servico_selecionado and 'SERVICO' in chamados_para_exportar_df.columns:
        chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['SERVICO'] == servico_selecionado]
    
    if tipo_chamado_selecionado and 'TIPOCHAMADO' in chamados_para_exportar_df.columns:
        chamados_para_exportar_df = chamados_para_exportar_df[chamados_para_exportar_df['TIPOCHAMADO'] == tipo_chamado_selecionado]

    if chamados_para_exportar_df.empty:
        # Poderia retornar uma mensagem ou redirecionar, mas para exportação,
        # um arquivo vazio ou uma mensagem de erro é mais apropriado.
        # Por simplicidade, vamos permitir um arquivo Excel vazio se for o caso.
        print("Nenhum dado para exportar após filtros.")

    # --- Preparar o arquivo Excel em memória ---
    output = io.BytesIO()
    # Usar with para garantir que o writer seja fechado corretamente
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Remover colunas que são objetos de data/hora brutos ou formatadas apenas para HTML, se desejar
        # Exemplo: df_to_export = chamados_para_exportar_df.drop(columns=['DT_ABERTURA_RAW', 'DT_ABERTURA_FORMATADA'], errors='ignore')
        # Ou selecionar apenas as colunas que você quer no Excel:
        colunas_para_exportar = [
            'CHAMADO', 'TITULO', 'SOLICITANTE', 'DEPARTAMENTO', 'UNIDADE', 
            'SERVICO', 'TEMA', 'TIPOCHAMADO', 'TEMPLATE', 'GRUPO', 
            'CATEGORIA', 'PRIORIDADE', 'ATENDENTE', 'DESCRICAO', 
            'PRAZO_HORAS', 'STATUS_CHAMADO', # STATUS_CHAMADO já é calculado em get_chamados
            # Para datas, vamos formatar como string DD-MM-YYYY para consistência com o que o usuário via no SQL original
            # Se a coluna DT_ABERTURA_RAW existe e é datetime, formatá-la.
        ]
        
        df_export = pd.DataFrame() # DataFrame vazio para o caso de não ter colunas
        
        if not chamados_para_exportar_df.empty:
            # Filtrar colunas existentes no DataFrame
            colunas_existentes = [col for col in colunas_para_exportar if col in chamados_para_exportar_df.columns]
            df_export = chamados_para_exportar_df[colunas_existentes].copy()

            # Formatar colunas de data/hora que vêm como objetos e queremos como string no Excel
            date_cols_raw = [col for col in chamados_para_exportar_df.columns if 'DT_' in col and '_RAW' in col]
            for col_raw in date_cols_raw:
                col_export_name = col_raw.replace('_RAW', '').replace('DT_', 'DATA_') # ex: DATA_ABERTURA
                if col_raw in chamados_para_exportar_df.columns: # Checa se a coluna raw existe
                    df_export[col_export_name] = pd.to_datetime(chamados_para_exportar_df[col_raw], errors='coerce').dt.strftime('%d-%m-%Y')

            time_cols_raw = [col for col in chamados_para_exportar_df.columns if 'HORA_' in col and '_RAW' in col]
            for col_raw in time_cols_raw:
                col_export_name = col_raw.replace('_RAW', '') # ex: HORA_ABERTURA
                if col_raw in chamados_para_exportar_df.columns:
                    # Objetos Time podem precisar de tratamento especial para .strftime, ou converter para string
                    df_export[col_export_name] = chamados_para_exportar_df[col_raw].astype(str)


        df_export.to_excel(writer, index=False, sheet_name='Chamados')
        
        # Ajustar largura das colunas (opcional, mas melhora a leitura)
        workbook  = writer.book
        worksheet = writer.sheets['Chamados']
        for i, col in enumerate(df_export.columns):
            column_len = max(df_export[col].astype(str).map(len).max(), len(col))
            # Limitar a largura máxima para não ficar excessivamente largo
            worksheet.set_column(i, i, min(column_len + 2, 50))


    excel_data = output.getvalue()
    # output.close() # BytesIO não precisa de close() explícito se usado com getvalue()

    # Nome do arquivo dinâmico com base nas datas
    filename = f"chamados_{data_inicio_str}_a_{data_fim_str}.xlsx"

    return Response(
        excel_data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)