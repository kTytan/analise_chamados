# app.py
from flask import Flask, render_template, request, url_for # Adicionado 'url_for'
from data_handler import get_chamados
from datetime import date, timedelta
import pandas as pd
import math # Para a função ceil (arredondar para cima)

app = Flask(__name__)

ITEMS_PER_PAGE = 50 # Definimos quantos itens por página

@app.route('/')
def index():
    # Obter datas do formulário
    data_inicio_form = request.args.get('data_inicio')
    data_fim_form = request.args.get('data_fim')

    # Obter número da página atual, padrão é 1
    page = request.args.get('page', 1, type=int)

    if data_inicio_form and data_fim_form:
        data_inicio_str = data_inicio_form
        data_fim_str = data_fim_form
    else:
        data_fim_dt = date(2025, 5, 13)
        data_inicio_dt = data_fim_dt - timedelta(days=30)
        data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
        data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    print(f"Filtros: Início: {data_inicio_str}, Fim: {data_fim_str}, Página: {page}")
    
     # Busca TODOS os chamados que correspondem ao filtro de data
    todos_chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)

    total_chamados_filtrados = 0
    chamados_pagina_df = pd.DataFrame() # DataFrame vazio por padrão
    total_pages = 0 # <--- INICIALIZAMOS total_pages AQUI

    if not todos_chamados_df.empty:
        total_chamados_filtrados = len(todos_chamados_df)
        
        # Calcular total de páginas
        total_pages = math.ceil(total_chamados_filtrados / ITEMS_PER_PAGE) # <--- CALCULAMOS total_pages AQUI
        
        # Garantir que a página solicitada não seja inválida
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0: 
            page = total_pages
        
        # Calcular índices para fatiar o DataFrame
        start_index = (page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        
        chamados_pagina_df = todos_chamados_df.iloc[start_index:end_index]

        if 'DT_ABERTURA_RAW' in chamados_pagina_df.columns:
            chamados_pagina_df.loc[:, 'DT_ABERTURA_FORMATADA'] = chamados_pagina_df['DT_ABERTURA_RAW'].apply(
                lambda x: x.strftime('%d-%m-%Y') if pd.notna(x) else ''
            )
    
    print(f"Total de chamados filtrados: {total_chamados_filtrados}, Exibindo página {page} de {total_pages}")

    return render_template('index.html',
                           chamados=chamados_pagina_df,
                           data_inicio=data_inicio_str,
                           data_fim=data_fim_str,
                           total_chamados=total_chamados_filtrados, 
                           page=page, 
                           total_pages=total_pages, # <--- E PASSAMOS total_pages AQUI
                           items_per_page=ITEMS_PER_PAGE)

if __name__ == '__main__':
    app.run(debug=True)