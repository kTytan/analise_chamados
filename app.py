# app.py
from flask import Flask, render_template
from data_handler import get_chamados # Importa nossa função
from datetime import date, timedelta   # Para trabalhar com datas
import pandas as pd # Importe pandas aqui

app = Flask(__name__) # Inicializa a aplicação Flask

@app.route('/') # Define a rota para a página inicial (ex: http://127.0.0.1:5000/)
def index():
    data_fim_dt = date(2025, 5, 13)
    data_inicio_dt = data_fim_dt - timedelta(days=30)

    data_inicio_str = data_inicio_dt.strftime('%Y-%m-%d')
    data_fim_str = data_fim_dt.strftime('%Y-%m-%d')

    print(f"Buscando dados para o período: {data_inicio_str} a {data_fim_str}")
    chamados_df = get_chamados(data_inicio=data_inicio_str, data_fim=data_fim_str, area_id=1)

    total_chamados_calculado = 0
    if not chamados_df.empty:
        total_chamados_calculado = len(chamados_df)
        # Pré-formatar a coluna de data para exibição
        # Isso evita lógica complexa de formatação no template e lida com NaT (Not a Time)
        if 'DT_ABERTURA_RAW' in chamados_df.columns:
            chamados_df['DT_ABERTURA_FORMATADA'] = chamados_df['DT_ABERTURA_RAW'].apply(
                lambda x: x.strftime('%d-%m-%Y') if pd.notna(x) else ''
            )
    
    print(f"Total de chamados para o template: {total_chamados_calculado}")
    print(f"Primeiras linhas do DataFrame (se houver):\n{chamados_df.head()}")

    return render_template('index.html',
                           chamados=chamados_df,
                           data_inicio=data_inicio_str,
                           data_fim=data_fim_str,
                           total_chamados=total_chamados_calculado)

if __name__ == '__main__':
    app.run(debug=True)