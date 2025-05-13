# data_handler.py
import mysql.connector
import pandas as pd
from config import DB_CONFIG  # Assume que DB_CONFIG tem database='softdesk' ou o usuário tem acesso
import numpy as np # Usaremos para o status
from datetime import date # Para tipos de data

# Mantemos a função de conexão
def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    try:
        # **IMPORTANTE**: Certifique-se que em config.py você tem 'database': 'softdesk'
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            return connection
    except mysql.connector.Error as e:
        print(f"Erro ao conectar ao MySQL ({e.errno}): {e.msg}")
        # Se for erro de acesso negado ao banco 'softdesk', avise o usuário
        if e.errno == 1044:
             print("Verifique se o usuário no config.py tem permissão para acessar o banco 'softdesk'.")
        elif e.errno == 1049:
             print(f"O banco de dados '{DB_CONFIG.get('database', 'N/A')}' especificado em config.py não foi encontrado.")
        return None

def get_chamados(data_inicio, data_fim, area_id=1):
    """
    Busca dados detalhados de chamados de um período e área específicos.

    Args:
        data_inicio (str ou date): Data de início no formato 'YYYY-MM-DD' ou objeto date.
        data_fim (str ou date): Data de fim no formato 'YYYY-MM-DD' ou objeto date.
        area_id (int): O ID da área para filtrar (padrão: 1).

    Returns:
        pandas.DataFrame: DataFrame com os dados dos chamados ou DataFrame vazio em caso de erro.
    """
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame() # Retorna DataFrame vazio se não houver conexão

    # Convertendo datas para string no formato correto para a query, se necessário
    if isinstance(data_inicio, date):
        data_inicio_str = data_inicio.strftime('%Y-%m-%d')
    else:
        data_inicio_str = data_inicio

    if isinstance(data_fim, date):
        data_fim_str = data_fim.strftime('%Y-%m-%d')
    else:
        data_fim_str = data_fim

    # SQL Query - Buscando datas/horas como tipos nativos
    # Selecionamos os campos mais relevantes do seu script original
    query = """
        SELECT
            c.cd_chamado AS CHAMADO,
            c.tt_chamado AS TITULO,
            u.nm_usuario AS SOLICITANTE,
            d.ds_departamento AS DEPARTAMENTO,
            f.nm_filial AS UNIDADE,
            s.ds_servico AS SERVICO,
            te.ds_template_chamado_tema AS TEMA,
            i.ds_tipo_chamado AS TIPOCHAMADO,
            t.tt_template_chamado AS TEMPLATE,
            g.ds_grupo_solucao AS GRUPO,
            e.ds_categoria AS CATEGORIA,
            p.ds_prioridade AS PRIORIDADE,
            a.nm_atendente AS ATENDENTE,
            c.ds_chamado AS DESCRICAO,
            p.tempo_solucao_prioridade AS PRAZO_HORAS, -- Renomeado para clareza
            c.da_chamado AS DT_ABERTURA_RAW,          -- Data de abertura (tipo DATE/DATETIME)
            c.ha_chamado AS HORA_ABERTURA_RAW,        -- Hora de abertura (tipo TIME)
            c.dt_atendimento_chamado AS DT_ATENDIMENTO_RAW,
            c.hr_atendimento_chamado AS HORA_ATENDIMENTO_RAW,
            c.dt_resolucao_chamado AS DT_RESOLUCAO_RAW,  -- Usaremos para calcular STATUS
            c.hr_resolucao_chamado AS HORA_RESOLUCAO_RAW,
            c.dt_fechamento_chamado AS DT_FECHAMENTO_RAW,
            c.hr_fechamento_chamado AS HORA_FECHAMENTO_RAW,
            c.dt_agendamento_chamado AS DT_AGENDAMENTO_RAW,
            c.sla_atendimento_porcentagem,
            c.sla_atendimento_tempo_decorrido,
            c.sla_atendimento_tempo_definido,
            c.sla_encaminhamento_tempo_decorrido
        FROM softdesk.sd_chamado c
        LEFT JOIN softdesk.sd_atendente a ON c.cd_atendente = a.cd_atendente
        LEFT JOIN softdesk.sd_area r ON c.cd_area = r.cd_area
        LEFT JOIN softdesk.sd_grupo_solucao g ON c.cd_grupo_solucao = g.cd_grupo_solucao
        LEFT JOIN softdesk.sd_filial f ON c.cd_filial = f.cd_filial
        LEFT JOIN softdesk.sd_servico s ON c.cd_servico = s.cd_servico
        LEFT JOIN softdesk.sd_departamento d ON c.cd_departamento = d.cd_departamento
        LEFT JOIN softdesk.sd_usuario u ON c.cd_usuario = u.cd_usuario
        LEFT JOIN softdesk.sd_template_chamado t ON c.cd_template = t.cd_template_chamado
        LEFT JOIN softdesk.sd_tipo_chamado i ON c.cd_tipo_chamado = i.cd_tipo_chamado
        LEFT JOIN softdesk.sd_prioridade p ON c.cd_prioridade = p.cd_prioridade
        LEFT JOIN softdesk.sd_categoria e ON c.cd_categoria = e.cd_categoria
        LEFT JOIN softdesk.sd_template_chamado_tema te ON c.cd_tema = te.cd_template_chamado_tema
        WHERE
            c.cd_area = %s
            AND c.da_chamado BETWEEN %s AND %s -- Usando BETWEEN para o intervalo de datas
    """

    # Parâmetros para a query (evita SQL injection)
    params = (area_id, data_inicio_str, data_fim_str)

    try:
        print(f"Executando query para Área: {area_id}, Período: {data_inicio_str} a {data_fim_str}")
        # Usar pd.read_sql para buscar os dados diretamente em um DataFrame
        df = pd.read_sql(query, conn, params=params)
        print(f"Consulta retornou {len(df)} registros.")

        # --- Pós-processamento com Pandas ---

        # 1. Calcular Status do Chamado
        # Se DT_RESOLUCAO_RAW não for Nulo/None/NaT, então 'FECHADO', senão 'ABERTO'
        df['STATUS_CHAMADO'] = np.where(pd.isna(df['DT_RESOLUCAO_RAW']), 'ABERTO', 'FECHADO')

        # 2. Converter colunas de data/hora para tipos corretos (se necessário)
        #    pd.read_sql geralmente tenta inferir os tipos, mas podemos forçar/verificar
        date_cols = [col for col in df.columns if 'DT_' in col and '_RAW' in col]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce') # 'coerce' transforma erros em NaT (Not a Time)

        time_cols = [col for col in df.columns if 'HORA_' in col and '_RAW' in col]
        for col in time_cols:
             # Timedeltas do MySQL (tipo TIME) podem vir como objetos timedelta do Python
             # Se precisar formatar para string HH:MM:SS pode fazer depois
             pass # Geralmente pd.read_sql já trata bem

        # 3. (Opcional) Formatar datas/horas para exibição (pode ser feito depois, na camada de apresentação)
        # Exemplo:
        # df['DT_ABERTURA_FORMATADA'] = df['DT_ABERTURA_RAW'].dt.strftime('%d-%m-%Y')
        # df['HORA_ABERTURA_FORMATADA'] = df['HORA_ABERTURA_RAW'].astype(str).str.split(' ').str[-1] # Ajuste conforme necessário

        return df

    except mysql.connector.Error as e:
        print(f"Erro ao executar query ou processar dados: {e}")
        return pd.DataFrame() # Retorna DataFrame vazio em caso de erro
    except Exception as e:
        print(f"Ocorreu um erro inesperado no Pandas: {e}")
        return pd.DataFrame()
    finally:
        # Certifica-se de que a conexão é fechada
        if conn and conn.is_connected():
            conn.close()
            # print("Conexão ao MySQL fechada.") # Opcional: remover se ficar muito verboso

def get_distinct_servicos():
    """Busca todos os serviços distintos para popular filtros."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    query = "SELECT cd_servico, ds_servico FROM softdesk.sd_servico ORDER BY ds_servico;"
    try:
        df = pd.read_sql(query, conn)
        return df
    except mysql.connector.Error as e:
        print(f"Erro ao buscar serviços distintos: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_distinct_tipos_chamado():
    """Busca todos os tipos de chamado distintos para popular filtros."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    query = "SELECT cd_tipo_chamado, ds_tipo_chamado FROM softdesk.sd_tipo_chamado ORDER BY ds_tipo_chamado;"
    try:
        df = pd.read_sql(query, conn)
        return df
    except mysql.connector.Error as e:
        print(f"Erro ao buscar tipos de chamado distintos: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()
def get_distinct_grupos_solucao():
    """Busca todos os grupos de solução distintos para popular filtros."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    # A sua query original usa g.ds_grupo_solucao AS GRUPO e c.cd_grupo_solucao
    query = "SELECT cd_grupo_solucao, ds_grupo_solucao FROM softdesk.sd_grupo_solucao ORDER BY ds_grupo_solucao;"
    try:
        df = pd.read_sql(query, conn)
        return df
    except mysql.connector.Error as e:
        print(f"Erro ao buscar grupos de solução distintos: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_distinct_unidades():
    """Busca todas as unidades (filiais) distintas para popular filtros."""
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    
    # A sua query original usa f.nm_filial AS UNIDADE e c.cd_filial
    query = "SELECT cd_filial, nm_filial FROM softdesk.sd_filial ORDER BY nm_filial;"
    try:
        df = pd.read_sql(query, conn)
        return df
    except mysql.connector.Error as e:
        print(f"Erro ao buscar unidades distintas: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    print("Testando a função get_chamados...")

    # Defina um período de teste (use datas relevantes para seus dados)
    # Lembre-se que a data atual é 2025-05-12
    data_inicio_teste = '2025-04-01'
    data_fim_teste = '2025-05-12'
    area_teste = 1

    chamados_df = get_chamados(data_inicio_teste, data_fim_teste, area_teste)

    if not chamados_df.empty:
        print("\n--- Primeiros 5 registros encontrados ---")
        print(chamados_df.head())
        print("\n--- Informações do DataFrame ---")
        chamados_df.info()
        print("\n--- Contagem de Status ---")
        print(chamados_df['STATUS_CHAMADO'].value_counts())
    else:
        print("\nNenhum dado encontrado para o período/área ou ocorreu um erro.")