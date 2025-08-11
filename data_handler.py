# data_handler.py
import mysql.connector
import pandas as pd
from config import DB_CONFIG

def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            return connection
    except mysql.connector.Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None

def get_chamados(data_inicio, data_fim, area_id=1, date_filter_type='abertura'):
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()

    date_field = "c.da_chamado" # Padrão
    if date_filter_type == 'resolucao':
        date_field = "c.dt_resolucao_chamado"
    
    query = f"""
        SELECT
            c.cd_chamado AS CHAMADO, c.tt_chamado AS TITULO,
            u.nm_usuario AS SOLICITANTE, d.ds_departamento AS DEPARTAMENTO,
            f.nm_filial AS UNIDADE, s.ds_servico AS SERVICO,
            i.ds_tipo_chamado AS TIPOCHAMADO, g.ds_grupo_solucao AS GRUPO,
            p.tempo_solucao_prioridade AS PRAZO_HORAS,
            c.da_chamado AS DT_ABERTURA_RAW, c.ha_chamado AS HORA_ABERTURA_RAW,
            c.dt_resolucao_chamado AS DT_RESOLUCAO_RAW,
            c.sla_resolucao_tempo_decorrido AS TEMPO_RESOLUCAO_DECORRIDO,
            c.sla_atendimento_tempo_definido, c.sla_encaminhamento_tempo_decorrido,
            c.sla_atendimento_tempo_decorrido,
            a.nm_atendente AS ATENDENTE,
            st.ds_status_chamado AS STATUS
        FROM softdesk.sd_chamado c
        LEFT JOIN softdesk.sd_atendente a           ON c.cd_atendente = a.cd_atendente
        LEFT JOIN softdesk.sd_grupo_solucao g       ON c.cd_grupo_solucao = g.cd_grupo_solucao
        LEFT JOIN softdesk.sd_filial f              ON c.cd_filial = f.cd_filial
        LEFT JOIN softdesk.sd_servico s             ON c.cd_servico = s.cd_servico
        LEFT JOIN softdesk.sd_departamento d        ON c.cd_departamento = d.cd_departamento
        LEFT JOIN softdesk.sd_usuario u             ON c.cd_usuario = u.cd_usuario
        LEFT JOIN softdesk.sd_tipo_chamado i        ON c.cd_tipo_chamado = i.cd_tipo_chamado
        LEFT JOIN softdesk.sd_prioridade p          ON c.cd_prioridade = p.cd_prioridade
        LEFT JOIN softdesk.sd_status_chamado st     ON c.st_chamado = st.cd_status_chamado
        WHERE
            c.cd_area = %s
            AND {date_field} BETWEEN %s AND %s 
    """
    params = (area_id, data_inicio, data_fim)
    try:
        df = pd.read_sql(query, conn, params=params)
        date_cols = [col for col in df.columns if 'DT_' in col and '_RAW' in col]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception as e:
        print(f"Erro ao executar query get_chamados: {e}")
        return pd.DataFrame()
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_distinct_servicos():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT ds_servico FROM softdesk.sd_servico ORDER BY ds_servico;"
    try: return pd.read_sql(query, conn)
    except Exception as e: print(f"Erro get_distinct_servicos: {e}"); return pd.DataFrame()
    finally:
        if conn and conn.is_connected(): conn.close()

def get_distinct_tipos_chamado():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT ds_tipo_chamado FROM softdesk.sd_tipo_chamado ORDER BY ds_tipo_chamado;"
    try: return pd.read_sql(query, conn)
    except Exception as e: print(f"Erro get_distinct_tipos_chamado: {e}"); return pd.DataFrame()
    finally:
        if conn and conn.is_connected(): conn.close()

def get_distinct_grupos_solucao():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT ds_grupo_solucao FROM softdesk.sd_grupo_solucao ORDER BY ds_grupo_solucao;"
    try: return pd.read_sql(query, conn)
    except Exception as e: print(f"Erro get_distinct_grupos_solucao: {e}"); return pd.DataFrame()
    finally:
        if conn and conn.is_connected(): conn.close()

def get_distinct_unidades():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT nm_filial FROM softdesk.sd_filial ORDER BY nm_filial;"
    try: return pd.read_sql(query, conn)
    except Exception as e: print(f"Erro get_distinct_unidades: {e}"); return pd.DataFrame()
    finally:
        if conn and conn.is_connected(): conn.close()

def get_distinct_status_chamado():
    conn = get_db_connection()
    if not conn: return []
    query = "SELECT DISTINCT ds_status_chamado FROM softdesk.sd_status_chamado ORDER BY ds_status_chamado;"
    try:
        df = pd.read_sql(query, conn)
        return df['ds_status_chamado'].tolist() if not df.empty else []
    except Exception as e: print(f"Erro get_distinct_status_chamado: {e}"); return []
    finally:
        if conn and conn.is_connected(): conn.close()