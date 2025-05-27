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
        print(f"Erro ao conectar ao MySQL ({e.errno}): {e.msg}")
        if e.errno == 1044:
             print("Verifique se o usuário no config.py tem permissão para acessar o banco especificado.")
        elif e.errno == 1049:
             print(f"O banco de dados '{DB_CONFIG.get('database', 'N/A')}' especificado em config.py não foi encontrado.")
        return None
    return None

def get_chamados(data_inicio, data_fim, area_id=1):
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()

    query = """
        SELECT
            c.cd_chamado 				AS CHAMADO, 
            c.tt_chamado 				AS TITULO,
            u.nm_usuario 				AS SOLICITANTE, 
            d.ds_departamento 			AS DEPARTAMENTO,
            f.nm_filial 				AS UNIDADE, 
            s.ds_servico 				AS SERVICO,
            te.ds_template_chamado_tema AS TEMA, 
            i.ds_tipo_chamado 			AS TIPOCHAMADO,
            t.tt_template_chamado 		AS TEMPLATE, 
            g.ds_grupo_solucao 			AS GRUPO,
            e.ds_categoria 				AS CATEGORIA, 
            p.ds_prioridade 			AS PRIORIDADE,
            a.nm_atendente 				AS ATENDENTE, 
            c.ds_chamado 				AS DESCRICAO,
            p.tempo_solucao_prioridade 	AS PRAZO_HORAS,
            c.da_chamado 				AS DT_ABERTURA_RAW, 
            c.ha_chamado 				AS HORA_ABERTURA_RAW,
            c.dt_atendimento_chamado 	AS DT_ATENDIMENTO_RAW, 
            c.hr_atendimento_chamado 	AS HORA_ATENDIMENTO_RAW,
            c.dt_resolucao_chamado 		AS DT_RESOLUCAO_RAW, 
            c.hr_resolucao_chamado 		AS HORA_RESOLUCAO_RAW,
            c.dt_fechamento_chamado 	AS DT_FECHAMENTO_RAW, 
            c.hr_fechamento_chamado 	AS HORA_FECHAMENTO_RAW,
            c.dt_agendamento_chamado 	AS DT_AGENDAMENTO_RAW,
            c.sla_atendimento_porcentagem, 
            c.sla_atendimento_tempo_decorrido,
            c.sla_atendimento_tempo_definido, 
            c.sla_encaminhamento_tempo_decorrido,
            c.st_chamado 				AS CD_STATUS, 
            st.ds_status_chamado 		AS STATUS
        FROM softdesk.sd_chamado c
        LEFT JOIN softdesk.sd_atendente a           ON c.cd_atendente = a.cd_atendente
        LEFT JOIN softdesk.sd_area r                ON c.cd_area = r.cd_area
        LEFT JOIN softdesk.sd_grupo_solucao g       ON c.cd_grupo_solucao = g.cd_grupo_solucao
        LEFT JOIN softdesk.sd_filial f              ON c.cd_filial = f.cd_filial
        LEFT JOIN softdesk.sd_servico s             ON c.cd_servico = s.cd_servico
        LEFT JOIN softdesk.sd_departamento d        ON c.cd_departamento = d.cd_departamento
        LEFT JOIN softdesk.sd_usuario u             ON c.cd_usuario = u.cd_usuario
        LEFT JOIN softdesk.sd_template_chamado t    ON c.cd_template = t.cd_template_chamado
        LEFT JOIN softdesk.sd_tipo_chamado i        ON c.cd_tipo_chamado = i.cd_tipo_chamado
        LEFT JOIN softdesk.sd_prioridade p          ON c.cd_prioridade = p.cd_prioridade
        LEFT JOIN softdesk.sd_categoria e           ON c.cd_categoria = e.cd_categoria
        LEFT JOIN softdesk.sd_template_chamado_tema te ON c.cd_tema = te.cd_template_chamado_tema
        LEFT JOIN softdesk.sd_status_chamado st     ON c.st_chamado = st.cd_status_chamado
        WHERE
            c.cd_area = %s
            AND c.da_chamado BETWEEN %s AND %s
    """
    params = (area_id, data_inicio, data_fim)
    try:
        df = pd.read_sql(query, conn, params=params)
        date_cols = [col for col in df.columns if 'DT_' in col and '_RAW' in col]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        
        if 'STATUS' not in df.columns and not df.empty:
            print("ALERTA DH: Coluna 'STATUS' não encontrada no DataFrame! Verifique a query SQL.")
            df['STATUS'] = 'Status Desconhecido' 
        elif df.empty and 'STATUS' not in df.columns: 
            df['STATUS'] = pd.Series(dtype='object')

        return df
    except mysql.connector.Error as e:
        print(f"Erro ao executar query get_chamados: {e}")
        return pd.DataFrame(columns=['CHAMADO', 'TITULO', 'STATUS']) 
    except Exception as e:
        print(f"Ocorreu um erro inesperado no Pandas em get_chamados: {e}")
        return pd.DataFrame(columns=['CHAMADO', 'TITULO', 'STATUS'])
    finally:
        if conn and conn.is_connected():
            conn.close()

def get_distinct_servicos():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT cd_servico, ds_servico FROM softdesk.sd_servico ORDER BY ds_servico;"
    try: return pd.read_sql(query, conn)
    except Exception as e: print(f"Erro get_distinct_servicos: {e}"); return pd.DataFrame()
    finally:
        if conn and conn.is_connected(): conn.close()

def get_distinct_tipos_chamado():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT cd_tipo_chamado, ds_tipo_chamado FROM softdesk.sd_tipo_chamado ORDER BY ds_tipo_chamado;"
    try: return pd.read_sql(query, conn)
    except Exception as e: print(f"Erro get_distinct_tipos_chamado: {e}"); return pd.DataFrame()
    finally:
        if conn and conn.is_connected(): conn.close()

def get_distinct_grupos_solucao():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT cd_grupo_solucao, ds_grupo_solucao FROM softdesk.sd_grupo_solucao ORDER BY ds_grupo_solucao;"
    try: return pd.read_sql(query, conn)
    except Exception as e: print(f"Erro get_distinct_grupos_solucao: {e}"); return pd.DataFrame()
    finally:
        if conn and conn.is_connected(): conn.close()

def get_distinct_unidades():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    query = "SELECT cd_filial, nm_filial FROM softdesk.sd_filial ORDER BY nm_filial;"
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