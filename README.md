**Documentação do Projeto: Sistema de Dashboards de Chamados**
1. Visão Geral do Projeto
Este projeto é uma aplicação web construída com Flask e Pandas para analisar e visualizar dados de chamados de um sistema de help desk. A aplicação se conecta a um banco de dados MySQL, processa os dados e os exibe em várias páginas e dashboards interativos, incluindo:

Uma página inicial que funciona como um portal de navegação.

Uma tela de análise detalhada com filtros avançados para busca e exportação de dados.

Quatro dashboards de TV para monitoramento em tempo real de diferentes áreas e KPIs:

TV Oracle Detalhada: Foco em Incidentes vs. Outros Chamados do serviço Oracle.

TV Fornecedores: KPIs de sustentação para os grupos SEVEN e MMBIT.

TV Gerencial: Visão geral de alto nível dos chamados do serviço Oracle e KPIs por grupos DBP.

TV SLA: Análise de performance do SLA de Resolução com filtros interativos.

2. Estrutura dos Arquivos
O projeto segue uma estrutura padrão de aplicações Flask:

/analise_chamados/
|
|-- venv/                  # Ambiente virtual do Python
|
|-- static/                # Arquivos estáticos (CSS, JS, Imagens - se houver)
|   -- css/
|
|-- templates/             # Arquivos HTML do Jinja2
|   |-- index.html         # Página inicial (portal de dashboards)
|   |-- analise_detalhada.html # Página de filtros avançados e tabela de dados
|   |-- dashboard_tv_oracle.html
|   |-- dashboard_tv_fornecedores.html
|   |-- dashboard_tv_gerencial.html
|   |-- dashboard_tv_sla.html
|   |-- _export_button.html  # Componente reutilizável para o botão de exportar
|   -- _pagination_controls.html # Componente reutilizável para a paginação
|
|-- app.py                 # Arquivo principal da aplicação Flask (rotas e lógica principal)
|-- data_handler.py        # Módulo para acesso e busca de dados no banco de dados
|-- config.py              # Arquivo de configuração (ex: credenciais do banco de dados)
-- requirements.txt       # Lista de dependências Python do projeto
3. Componentes Principais
3.1. config.py (Configuração)
Este arquivo (que você deve criar) armazena as credenciais de conexão com o banco de dados de forma segura, separadas do código principal.

Exemplo:
# config.py
DB_CONFIG = {
    'host': 'seu_host_do_banco',
    'user': 'seu_usuario',
    'password': 'sua_senha',
    'database': 'softdesk' # Ou o nome do seu banco
}

3.2. data_handler.py (Camada de Dados)
Este módulo é responsável por toda a comunicação com o banco de dados.

get_db_connection(): Estabelece e retorna uma conexão com o banco de dados MySQL.

get_chamados(data_inicio, data_fim, area_id, date_filter_type='abertura'):

Função principal e flexível de busca de dados.

Retorna um DataFrame Pandas com os chamados.

Filtra os chamados por um período de datas. O campo de data usado para o filtro é determinado pelo parâmetro date_filter_type:

'abertura' (padrão): Filtra pela data de abertura (c.da_chamado). Usado pela maioria das telas.

'resolucao': Filtra pela data de resolução (c.dt_resolucao_chamado). Usado pela tela de SLA.

get_distinct_...(): Funções auxiliares (get_distinct_servicos, get_distinct_status_chamado, etc.) que buscam listas de valores únicos para popular os dropdowns de filtro.

3.3. app.py (Lógica da Aplicação)
Este é o coração do projeto. Ele define as rotas (URLs) e a lógica para processar os dados e renderizar as páginas HTML.

Constantes Globais:

No topo do arquivo, definimos constantes para nomes de serviços (SERVICO_ORACLE), grupos (GRUPO_SUSTENTACAO_SEVEN, LISTA_GRUPOS_DBP), e todos os nomes de status (ex: STATUS_ENCERRADO).

STATUS_EM_ATENDIMENTO_LISTA e STATUS_FECHADO_LISTA são listas cruciais que agrupam vários status para facilitar o cálculo de KPIs. É fundamental que os nomes de status aqui correspondam 100% aos do banco de dados.

Rotas Principais:

@app.route('/') -> index(): Renderiza a index.html, que agora funciona como um portal de navegação para os outros dashboards.

@app.route('/analise_detalhada') -> analise_detalhada():

É a tela mais complexa e flexível.

Aceita múltiplos parâmetros de filtro pela URL (servico, tipo_chamado, grupo_solucao, status_chamado, e o novo date_type).

Usa request.args.getlist('status_chamado') para poder receber múltiplos status (essencial para o drill-down do KPI "Em Atendimento").

Chama get_chamados passando o date_filter_type para buscar por data de abertura ou resolução.

Exibe os resultados em uma tabela paginada.

@app.route('/dashboard_tv_sla') -> dashboard_tv_sla():

Exibe KPIs de SLA de Resolução.

Possui seletores interativos para Período, Tipo de Chamado e Serviço.

Chama get_chamados(..., date_filter_type='resolucao') para analisar chamados resolvidos no período selecionado.

Os KPIs são clicáveis e usam o url_for para criar um link de drill-down para a analise_detalhada, passando todos os filtros ativos, incluindo date_type='resolucao'.

@app.route('/dashboard_tv_fornecedores') -> dashboard_tv_fornecedores():

Exibe KPIs para os grupos "Sustentação - SEVEN" e "Solution - MMBIT".

Usa a função auxiliar calcular_dados_tv_fornecedores() para calcular um conjunto específico de KPIs focados em chamados ativos.

O KPI "Total em Aberto" é a soma de "Em Atendimento", "Aguardando Solicitante" e "Contestado".

@app.route('/dashboard_tv_oracle') -> dashboard_tv_oracle():

Exibe dois painéis: "Incidentes Oracle" e "Outros Chamados Oracle".

Cada painel tem um conjunto de 9 KPIs (incluindo contagens, Aging e Tempo Médio de Atendimento) e uma pizza de status.

A lógica de cálculo dos KPIs é feita diretamente dentro da função da rota, sem uma função auxiliar, para maior clareza.

@app.route('/dashboard_tv_gerencial') -> dashboard_tv_gerencial():

Exibe uma visão geral do serviço Oracle e KPIs para os grupos DBP.

A seção de KPIs dos grupos DBP é calculada sobre todos os serviços, conforme solicitado.

Inclui gráficos de linha mostrando a evolução de Incidentes e Requisições nos últimos 12 meses.

@app.route('/exportar_excel') -> exportar_excel():

Recebe os mesmos filtros da analise_detalhada e gera um arquivo .xlsx com os dados correspondentes.

3.4. Templates (HTML)
index.html: A página de entrada, com cards de navegação para as outras telas.

analise_detalhada.html: Contém o formulário com todos os filtros (incluindo o novo seletor de tipo de data), a tabela de resultados e os placeholders para gráficos.

dashboard_tv_...: Cada tela de TV tem seu próprio layout de CSS e estrutura HTML para exibir os KPIs e gráficos de forma otimizada para monitoramento. Usam o tema escuro.

_pagination_controls.html e _export_button.html: São componentes ("partials") incluídos em outras páginas para evitar repetição de código.

4. Como Executar o Projeto
Certifique-se de que o Python e o pip estão instalados.

Crie um ambiente virtual na pasta do projeto: python -m venv venv

Ative o ambiente virtual: venv\Scripts\activate (no Windows) ou source venv/bin/activate (no Linux/macOS).

Instale as dependências: pip install -r requirements.txt

Crie e configure o arquivo config.py com as credenciais do seu banco de dados.

Execute a aplicação: python app.py

Acesse http://127.0.0.1:5000 (ou o endereço que o Flask indicar) no seu navegador.
