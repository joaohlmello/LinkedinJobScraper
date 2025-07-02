import os
import json
import logging
import time
import re
import base64
from google import genai
from google.genai import types

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobAnalyzer:
    """
    Esta classe utiliza a API do Gemini para analisar descrições de vagas de emprego e
    calcular a compatibilidade com o currículo de um candidato.
    """
    
    def __init__(self):
        """
        Inicializa o analisador de vagas com a configuração da API do Gemini.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("Chave de API do Gemini não encontrada nas variáveis de ambiente.")
            raise ValueError("GEMINI_API_KEY não está definida nas variáveis de ambiente")
        
        try:
            # Inicializar cliente Gemini (usando vertexai=False para usar API key direta)
            self.client = genai.Client(
                api_key=api_key,
                vertexai=False
            )
            self.model_name = "gemini-2.5-flash-preview-04-17"
            
            # Configuração de geração
            self.generation_config = types.GenerateContentConfig(
                temperature=0,
                top_p=0.6,
                response_mime_type="application/json",
                response_schema=types.Schema(
                    type=types.Type.OBJECT,
                    required=["pontuacao_requisitos", "pontuacao_responsabilidades", "pontos_fracos"],
                    properties={
                        "pontuacao_requisitos": types.Schema(
                            type=types.Type.INTEGER,
                        ),
                        "pontuacao_responsabilidades": types.Schema(
                            type=types.Type.INTEGER,
                        ),
                        "pontos_fracos": types.Schema(
                            type=types.Type.STRING,
                        ),
                    },
                ),
            )
            
            # Configurar o prompt base
            self.system_prompt = self._get_system_prompt()
            
            logger.info(f"Analisador de vagas inicializado com o modelo {self.model_name}")
        except Exception as e:
            logger.error(f"Erro ao inicializar o cliente Gemini: {str(e)}")
            raise ValueError(f"Não foi possível inicializar o cliente Gemini: {str(e)}")
    
    def _get_system_prompt(self):
        """
        Retorna o prompt do sistema que orienta o modelo sobre como analisar as vagas.
        """
        return """#INSTRUÇÕES
-Execute as tarefas abaixo de forma direta e objetiva.
-Responda sempre em portugues.
-Apresente os resultados estritamente no formato especificado
-Seja rigoroso, como um Recrutador experiente e com centenas de candidatos bons seria. Você quer encontrar o candidato perfeito para a vaga.

#ENTRADAS
-DESCRIÇÃO DA VAGA (JD)
-CURRÍCULO (CV)

#Passo 1: Extrair TERMOS da JD
Identifique e liste os TERMOS da JD, agrupando nas categorias abaixo. Considere sinônimos e alternativas ("OU"). Se algum deles não for informado, será "N/A"
-Educação Formal e Certificações.
-Anos de Experiência no Cargo.
-Requisitos Obrigatórios e Desejáveis (Obs: Excluir itens já listados anteriormente)
-Responsabilidades e Atividades: (Obs: Excluir itens já listados anteriormente)

#Passo 2: Analise objetiva dos TERMOS (binário, atende completamente / não atende completamente)

#Passo 3: Apresentar Resultados (Formato Estrito)
Apresente a informação abaixo, sem nenhuma informação a mais. Utilize Rich text e Emojis (check verde, X vermelho, ! amarela) para facilitar a leitura.
##Pontuação por Categoria de TERMOS  (divida o total de TERMOS atendidos completamente pelo total de termos geral)
-Requisitos Obrigatórios e Desejáveis
-Responsabilidades e Atividades
##Lista de Pontos Fracos


#CV
SUMÁRIO
5 anos de experiência como Product Manager em todo o ciclo de vida de produtos digitais. Especializado em produtos de dados, plataforma, gestão e IA. Liderança de equipes multidisciplinares (17 diretos) e gestão de stakeholders estratégicos. 
Perfil  analítico e orientado a dados. Conhecimento técnico e forte utilização de SQL, inteligência artificial e no-code.
Alta capacidade de gerenciamento e execução utilizando metodologias ágeis (Scrum, Kanban). Inglês fluente.

EDUCAÇÃO
MBA | FGV – Fundação Getúlio Vargas | 10/2022
Graduação em Engenharia | Estácio | 06/2018

CERTIFICAÇÕES
PMP – Project Management Professional | PMI – Project Management Institute | 12/2020
SFPC – Scrum Professional Certificate | Certiprof | 06/2020

EXPERIÊNCIA PROFISSIONAL
ONCOCLÍNICAS (contratado)
Consultor, Product Management & Tecnologia | 01/2025 – 06/2025
Product Manager responsável pela idealização, discovery, desenvolvimento e implantação do produto interno de gestão integrada do portfólio de projetos. A solução que gera status reports automatizados em tempo real de 50 projetos (BRL 180MM), nas disciplinas de escopo, cronograma, custos, riscos e suprimentos. O produto conta com funcionalidade de inteligência artificial para análise e lançamento de notas fiscais. O tempo de reporte foi reduzido de 1 semana para tempo real, e o lead time de aprovações financeiras de 2 semanas para 3 dias.

SYNERGIA CONSULTORIA, Cliente VALE
Diretor, Product Management & Tecnologia | 10/2022 – 12/2024
Gerenciei o ciclo de vida completo de produtos, desde a concepção (discovery) até a entrega/lançamento (delivery), atuando como ponto focal na comunicação com clientes e stakeholders estratégicos, negociando trade-offs e alinhando expectativas. Reportei ao cliente (VALE), à CEO da consultoria e ao CEO do fundo de private equity (TPF – Bélgica).
Liderei uma equipe multidisciplinar de 17 pessoas (Product Manager, Designer, Desenvolvedores, Engenheiros de Dados), promovendo o desenvolvimento técnico e comportamental do time com 1:1s, PDIs e feedbacks, e influenciando indiretamente uma equipe de mais de 300 pessoas.
Defini e gerenciei KPIs e OKRs e apoiei a adoção de OKRs para toda a empresa. Identifiquei e implementei oportunidades de melhoria e inovação, principalmente relacionadas a dados, automações e inteligência artificial. Realizei pesquisas de mercado, principalmente relacionadas a inovações e soluções para as nossas plataformas.
Defini e comuniquei visão e estratégia dos produtos. Gerenciei e priorizei roadmaps e backlogs com RICE/MoSCoW e ROI. Analisei dados e métricas para tomada de decisão. Liderei processos de discovery para entender as dores do usuário. Desenvolvi e testei hipóteses com MVPs no-code antes de investir recursos. Traduzi necessidades de negócio em requisitos técnicos. Garanti a qualidade e o sucesso das entregas. Comuniquei o progresso e os resultados.
PRINCIPAIS RESULTADOS:
Liderança do turnaround do contrato com nosso maior cliente (BRL 100MM), reestruturando a área de Produto e Tecnologia, e atuando como  Product Manager hands-on, recuperando a confiança com entregas contínuas de valor.
Reestruturação da fábrica de software para squads de produto com práticas e ferramentas ágeis (discovery, PRD, stories, critérios de aceite, JIRA, Confluence, etc.), melhorando o alinhamento das entregas com as necessidades do negócio.
Desenvolvimento de plataforma para monitoramento de milhões de entregáveis de 400 mil usuários em centenas de etapas, com regras de negócio complexas e integração via API, reduzindo o tempo de reporte de 1 semana para tempo real, automatizando tarefas com scripts e IA, e gerando dashboards em PowerBI.
Reconstrução do produto core de e análise de dados socioeconômicos com integração offline to online (O2O), corrigindo problemas de UI, UX, bugs recorrentes, e viabilizando extração de dados e integrações, resultando em redução de 80% das ocorrências, e gerando a percepção de UI e UX mais ágil e intuitiva pelos usuários.
ONCOCLÍNICAS
Program Manager | 07/2021 – 10/2022
Gerenciei múltiplos projetos corporativos e de tecnologia, coordenando equipes internas e contratadas durante todo o ciclo de vida, e implementando processos estruturados para assegurar o atingimento de resultados de negócio.
Facilitei a comunicação com stakeholders e conduzi reuniões de status, garantindo alinhamento e gerenciando conflitos. Elaborei e apresentei relatórios gerenciais e executivos para tomada de decisão.
Identifiquei e implementei oportunidades de melhoria e inovação relacionadas a otimização de processos.
Desenvolvi e gerenciei roadmaps e cronogramas. Analisei dados e métricas para tomada de decisão. Liderei processos de discovery para entender as dores e necessidades do negócio. Desenvolvi e testei hipóteses com MVPs no-code. Traduzi necessidades de negócio em requisitos técnicos. Garanti a qualidade e o sucesso das entregas. Comuniquei o progresso e os resultados. Mapeei e gerenciei custos riscos dos projetos, executando ações corretivas e preventivas.  Conduzi cerimônias ágeis (Daily, Planning, Review, Retrospectiva).
PRINCIPAIS RESULTADOS:
Gestão 4 programas (BRL 18MM) com controle eficaz de prazo e custos, e nota máxima na avaliação de resultados.
Melhoria de Processos de Governança: Implementação de gestão de mudanças de escopo com fluxo de aprovação, mitigando riscos, evitando custos não apropriados e resolvendo problemas históricos de falta de controle.
Melhoria de Processos Operacionais: Implementação de sistema de checklist de transição para a operação, reduzindo não conformidades em 95%, aumentando a satisfação do cliente e garantindo a qualidade.  Conduzi cerimônias ágeis (Daily, Planning, Review, Retrospectiva).

EQSEED, Top 100 Startups to Watch
Product Manager| 02/2020 – 07/2021
Liderei a transformação digital em uma fintech marketplace, com reporte direto ao CEO de naturalidade inglesa.
Implementei metodologias ágeis (Kanban) e OKRs em toda a empresa (Tecnologia, Negócios, Marketing), conectando estratégia à execução, e viabilizando a priorização do backlog de maneira integrada. Identifiquei oportunidades de melhoria através de discovery com usuários e áreas de negócio. Realizei pesquisas de mercado e concorrência.
Gerenciei e priorizei roadmaps e backlogs. Analisei dados e métricas para tomada de decisão. Desenvolvi MVPs no-code. Traduzi necessidades de negócio em requisitos técnicos. Garanti a qualidade e o sucesso das entregas. Comuniquei o progresso e os resultados. Analisei dados e construí dashboards e BIs para guiar a tomada de decisão.
Acompanhei métricas e KPIs como NPS, CAC, LTV e churn
PRINCIPAIS RESULTADOS:
Premiação expressiva em equity (0.2%) devido a meta atingida de faturamento durante a crise do COVID-19.
Reestruturação do CRM: Redesenho de processos e automações. Aumento de 15% na conversão de leads.
Automação do Pós–vendas: Automação de processos e melhorias de UI/UX, reduzindo o tempo de assinatura de contratos e melhorando a experiência do usuário. NPS elevado a zona de excelência, acima de 75.
Automação da Reconciliação Financeira: Reduzindo em 80% o lead time e eliminando erros operacionais.
Sistematização da Análise de Investimentos e do Valuation do Portfólio: Aumentando a eficiência operacional.

CARGOS ANTERIORES
03/2018 – 08/2019 | N&A CONSULTORES, Cliente BRMALLS | Coordenador de Planejamento & Controle de Projetos
08/2017 – 03/2018 | N&A CONSULTORES, Cliente BRMALLS | Analista de Planejamento & Controle de Projetos
11/2016 – 08/2017 | ONCOCLÍNICAS                                          | Estagiário de PMO
07/2015 – 06/2016 | N&A CONSULTORES, Cliente BRMALLS | Estagiário de Planejamento & Controle de Projetos

COMPETÊNCIAS
Idiomas: Inglês fluente/avançado.	
Metodologias e Frameworks: Metodologias Ágeis (Scrum, Kanban), OKR, Design Thinking, OKR, Jobs To Be Done (JTD), BPM/BPMN.
Gestão de Projetos e Colaboração: JIRA, Confluence, Azure Devops, Asana, ClickUp, Notion, Trello, Figma, Miro, Mural.
Análise de Dados e Business Intelligence: SQL, Power BI, Looker Studio, Metabase.
AI & Automação: APIs OpenAI e Gemini API, MCP, RPA, Low-code, No-code (Power Automate, N8N, Supabase, Python/Replit, Lovable,Github, etc.).
ERP e Gestão de Serviços: SAP S/4HANA, TOTVS, Fluig, ServiceNow.
Pacote Office: Excel avançado (procv, tabelas dinâmicas, VBA, etc.), PowerPoint, etc.
"""

    def analyze_job(self, job_data):
        """
        Analisa uma vaga de emprego usando a API do Gemini.
        
        Args:
            job_data (dict): Dicionário contendo os dados da vaga
                Exemplo: {
                    'job_title': 'Gerente de Projetos',
                    'company_name': 'Empresa XYZ',
                    'job_description': 'Descrição completa da vaga...',
                    'link': 'https://www.linkedin.com/jobs/view/123456789'
                }
                
        Returns:
            dict: Resultado da análise com notas e recomendações
        """
        if not job_data or 'job_description' not in job_data:
            logger.warning("Dados de vaga inválidos ou sem descrição")
            return {
                "error": "Dados de vaga inválidos ou incompletos"
            }
            
        try:
            # Preparar o conteúdo para enviar ao Gemini
            job_title = job_data.get('job_title', 'Não informado')
            company_name = job_data.get('company_name', 'Não informado') 
            job_description = job_data.get('job_description', '')
            job_link = job_data.get('link', 'Não informado')
            
            # Limpar a descrição da vaga para remover tags HTML
            clean_description = job_description.replace('<br><br>', '\n\n').replace('<br>', '\n')
            
            # Construir o prompt do usuário para análise
            input_text = f"""
# VAGA: {job_title}
# EMPRESA: {company_name}

# DESCRIÇÃO DA VAGA:
{clean_description}

Analisar a compatibilidade entre o currículo do candidato modelo (fornecido no seu contexto) e esta vaga de emprego.
            """
            
            # Fazer a chamada à API do Gemini
            logger.info(f"Enviando solicitação de análise para vaga: {job_title}")
            
            try:
                # Preparar o conteúdo como Content struct
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=input_text),
                        ],
                    ),
                ]
                
                # Adicionar system_instruction ao config
                self.generation_config.system_instruction = [
                    types.Part.from_text(text=self.system_prompt)
                ]
                
                # Gerar conteúdo - seguindo exatamente o exemplo fornecido
                response_stream = self.client.models.generate_content_stream(
                    model=self.model_name,
                    contents=contents,
                    config=self.generation_config,
                )
                
                # Coletar todo o texto da resposta
                result_json = ""
                for chunk in response_stream:
                    if chunk.text:
                        result_json += chunk.text
                
            except Exception as e:
                logger.error(f"Erro na chamada à API do Gemini: {str(e)}")
                raise Exception(f"Falha na análise com Gemini API: {str(e)}")
            
            # Analisar e retornar o resultado
            if result_json:
                try:
                    # Tentar extrair o JSON da resposta, verificando se há código de formatação
                    # ao redor da resposta JSON
                    json_content = result_json
                    
                    # Tentar encontrar conteúdo JSON entre marcadores de código
                    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', result_json)
                    if json_match:
                        json_content = json_match.group(1).strip()
                        logger.info("Encontrado JSON entre marcadores de código")
                    
                    # Se não encontrar entre marcadores de código, procurar por chaves { } externas
                    if not json_match:
                        json_match = re.search(r'(\{[\s\S]*\})', result_json)
                        if json_match:
                            json_content = json_match.group(1).strip()
                            logger.info("Encontrado JSON entre chaves externas")
                    
                    # Processar o resultado como JSON
                    analysis_data = json.loads(json_content)
                    
                    # Mapear campos para manter compatibilidade com o código existente
                    if "pontuacao_requisitos" in analysis_data:
                        analysis_data["nota_requisitos"] = analysis_data["pontuacao_requisitos"]
                    
                    if "pontuacao_responsabilidades" in analysis_data:
                        analysis_data["nota_responsabilidades"] = analysis_data["pontuacao_responsabilidades"]
                    
                    # Adicionar informações de sistema às análises para exibição
                    analysis_data["system_instructions"] = self.system_prompt
                    analysis_data["job_link"] = job_link
                    
                    # Retornar o resultado processado
                    return analysis_data
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Erro ao decodificar JSON: {str(e)}")
                    logger.error(f"Conteúdo recebido: {result_json}")
                    return {
                        "error": "Resposta inválida do Gemini (formato JSON inválido)",
                        "raw_response": result_json
                    }
            else:
                return {
                    "error": "Resposta vazia do Gemini"
                }
                
        except Exception as e:
            logger.error(f"Erro ao analisar vaga: {str(e)}")
            return {
                "error": f"Erro ao analisar vaga: {str(e)}"
            }
    
    def analyze_jobs_batch(self, jobs_data, max_retries=5, delay_between_calls=2, progress_callback=None):
        """
        Analisa um lote de vagas de emprego.
        
        Args:
            jobs_data (list): Lista de dicionários contendo os dados das vagas
            max_retries (int): Número máximo de tentativas em caso de erro
            delay_between_calls (int): Tempo de espera entre chamadas para evitar limites de API
            progress_callback (function, optional): Função de callback para atualizar o progresso
                com assinatura (current, total, message)
            
        Returns:
            list: Lista de resultados de análise para cada vaga
        """
        results = []
        total_jobs = len(jobs_data)
        
        for i, job_data in enumerate(jobs_data):
            current = i + 1
            job_title = job_data.get('job_title', 'Sem título')
            
            # Atualizar progresso
            if progress_callback:
                progress_callback(current, total_jobs, f"Analisando vaga {current}/{total_jobs}: {job_title}")
            
            # Tentativas com retry
            retry_count = 0
            success = False
            result = None
            
            while not success and retry_count < max_retries:
                try:
                    result = self.analyze_job(job_data)
                    
                    # Verificar se houve erro específico na análise
                    if "error" in result:
                        retry_count += 1
                        error_msg = result.get("error", "Erro desconhecido")
                        logger.warning(f"Tentativa {retry_count}/{max_retries} falhou: {error_msg}")
                        
                        if retry_count < max_retries:
                            # Esperar tempo progressivo entre tentativas (backoff exponencial)
                            wait_time = delay_between_calls * (2 ** (retry_count - 1))
                            logger.info(f"Aguardando {wait_time}s antes da próxima tentativa...")
                            time.sleep(wait_time)
                        else:
                            # Se esgotaram as tentativas, aceitar o resultado com erro
                            success = True
                    else:
                        # Sucesso na análise
                        success = True
                
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Erro na tentativa {retry_count}/{max_retries}: {str(e)}")
                    
                    if retry_count < max_retries:
                        # Esperar antes da próxima tentativa
                        wait_time = delay_between_calls * (2 ** (retry_count - 1))
                        logger.info(f"Aguardando {wait_time}s antes da próxima tentativa...")
                        time.sleep(wait_time)
                    else:
                        # Se esgotaram as tentativas, criar um resultado de erro
                        result = {
                            "error": f"Erro após {max_retries} tentativas: {str(e)}"
                        }
                        success = True  # Para sair do loop
            
            # Adicionar o resultado à lista
            results.append(result)
            
            # Esperar entre chamadas para evitar rate limits
            if i < total_jobs - 1:  # Não esperar após o último item
                time.sleep(delay_between_calls)
        
        return results

def format_text_with_breaks(text):
    """
    Formata texto substituindo quebras de linha por tags HTML <br>.
    Isso evita problemas com f-strings contendo caracteres de escape.
    
    Args:
        text (str): Texto a ser formatado
        
    Returns:
        str: Texto formatado com tags <br>
    """
    if not text:
        return ""
    return text.replace('\n', '<br>')

def format_analysis_html(analysis):
    """
    Formata o resultado da análise em HTML para exibição na interface.
    
    Args:
        analysis (dict): Resultado da análise do Gemini
        
    Returns:
        str: HTML formatado para exibição
    """
    if "error" in analysis:
        return f"""
        <div class="alert alert-danger">
            <strong>Erro na análise:</strong> {analysis['error']}
        </div>
        """
    
    # Obter valores das análises ou usar placeholder
    nota_requisitos = analysis.get('nota_requisitos', analysis.get('pontuacao_requisitos', 'N/A'))
    nota_responsabilidades = analysis.get('nota_responsabilidades', analysis.get('pontuacao_responsabilidades', 'N/A'))
    pontos_fracos = format_text_with_breaks(analysis.get('pontos_fracos', 'Não informado'))
    
    # Definir classes para estilização de compatibilidade
    compat_class = ""
    if isinstance(nota_requisitos, (int, float)):
        if nota_requisitos >= 90:
            compat_class = "compatibility-excellent"
        elif nota_requisitos >= 75:
            compat_class = "compatibility-good"
        elif nota_requisitos >= 50:
            compat_class = "compatibility-medium"
        else:
            compat_class = "compatibility-low"
    
    return f"""
    <div class="analysis-container">
        <div class="row">
            <div class="col-md-6">
                <h5>Compatibilidade</h5>
                <div class="lead mb-2 {compat_class}">
                    <strong>{nota_requisitos}</strong>
                </div>
                <div class="small text-muted">Pontuação de Requisitos</div>
            </div>
            <div class="col-md-6">
                <h5>Responsabilidades</h5>
                <div class="lead mb-2">
                    <strong>{nota_responsabilidades}</strong>
                </div>
                <div class="small text-muted">Pontuação de Responsabilidades</div>
            </div>
        </div>
        <hr>
        <div class="row mt-3">
            <div class="col-12">
                <h5>Pontos de Atenção</h5>
                <div class="analysis-detail">
                    {pontos_fracos}
                </div>
            </div>
        </div>
    </div>
    """

def format_jobs_table_html(job_analyses):
    """
    Formata uma lista de análises de vagas como uma tabela HTML.
    
    Args:
        job_analyses (list): Lista de análises de vagas
        
    Returns:
        str: HTML da tabela com os resultados
    """
    rows = []
    
    for job in job_analyses:
        # Dados básicos da vaga
        job_title = job.get('job_title', 'Não informado')
        job_url = job.get('link', '#')
        company_name = job.get('company_name', 'Não informado')
        company_url = job.get('company_link', '#')
        
        # Dados da análise do Gemini (se disponível)
        analysis = job.get('analysis', {})
        
        # Obter valores usando qualquer um dos nomes de campo (antigo ou novo)
        nota_requisitos = analysis.get('nota_requisitos', analysis.get('pontuacao_requisitos', 'N/A'))
        nota_responsabilidades = analysis.get('nota_responsabilidades', analysis.get('pontuacao_responsabilidades', 'N/A'))
        pontos_fracos = format_text_with_breaks(analysis.get('pontos_fracos', 'N/A'))
        
        # Definir classe de compatibilidade com base na nota
        compat_class = ""
        if isinstance(nota_requisitos, (int, float)):
            if nota_requisitos >= 90:
                compat_class = "text-success"
            elif nota_requisitos >= 75:
                compat_class = "text-info"
            elif nota_requisitos >= 50:
                compat_class = "text-warning"
            else:
                compat_class = "text-danger"
        
        # Criar linha da tabela
        row = f"""
        <tr>
            <td>
                <a href="{job_url}" target="_blank">{job_title}</a>
                <div class="small text-muted">
                    <a href="{company_url}" target="_blank">{company_name}</a>
                </div>
            </td>
            <td class="{compat_class}">{nota_requisitos}</td>
            <td>{nota_responsabilidades}</td>
            <td>{pontos_fracos}</td>
        </tr>
        """
        
        rows.append(row)
    
    # Montar a tabela completa
    table = f"""
    <table class="table table-striped">
        <thead>
            <tr>
                <th>Vaga / Empresa</th>
                <th>Pontuação Requisitos</th>
                <th>Pontuação Responsabilidades</th>
                <th>Pontos Fracos</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
    """
    
    return table