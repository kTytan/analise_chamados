# app.py
from flask import Flask, render_template, request, url_for
from data_handler import get_chamados
from datetime import date, timedelta
import pandas as pd
import math
import plotly.express as px # Importar Plotly Express

app = Flask(__name__)

ITEMS_PER_PAGE = 50

@app.route('/')
def index():
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')
    page = request.args.get('page', 1, type=int)

    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        # Usando a data atual do sistema para o padrão
        # (terça-feira, 13 de maio de 2025, 09:24:27 AM -03)
        data_fim_dt = date.today() # Data atual real do servidor
        data_inicio_dt = data_fim_dt - timedelta(days=29) # Últimos 30 dias (incluindo hoje)
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
        data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    print(f"Filtros: Início: {data_inicio_str}, Fim: {data_fim_str}, Página: {page}")
    
    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)

    total_chamados_filtrados = 0
    chamados_pagina_df = pd.DataFrame()
    total_pages = 0
    status_graph_html = None # Inicializa como None

    if not todos_chamados_df.empty:
        total_chamados_filtrados = len(todos_chamados_df)
        total_pages = math.ceil(total_chamados_filtrados / ITEMS_PER_PAGE)
        
        if page < 1: page = 1
        elif page > total_pages and total_pages > 0: page = total_pages
        
        start_index = (page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        chamados_pagina_df = todos_chamados_df.iloc[start_index:end_index].copy() # Usar .copy() para evitar SettingWithCopyWarning

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
                    color_discrete_map={'ABERTO': 'orange', 'FECHADO': 'green'} # Cores personalizadas
                )
                fig_status.update_layout(
                    margin=dict(l=20, r=20, t=50, b=20), # Ajusta margens
                    height=400 # Altura do gráfico
                )
                # Converte o gráfico para HTML (sem o HTML completo, apenas o div do gráfico)
                # include_plotlyjs='cdn' garante que o JS do Plotly seja carregado da internet
                status_graph_html = fig_status.to_html(full_html=False, include_plotlyjs='cdn')
    
    print(f"Total de chamados filtrados: {total_chamados_filtrados}, Exibindo página {page} de {total_pages}")

    return render_template('index.html',
                           chamados=chamados_pagina_df,
                           data_inicio=data_inicio_str,
                           data_fim=data_fim_str,
                           total_chamados=total_chamados_filtrados,
                           page=page,
                           total_pages=total_pages,
                           items_per_page=ITEMS_PER_PAGE,
                           status_graph_html=status_graph_html) # Passa o HTML do gráfico

if __name__ == '__main__':
    app.run(debug=True)