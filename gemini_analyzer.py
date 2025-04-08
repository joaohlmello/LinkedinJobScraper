import os
import json
import logging
import time
import re
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
            # Inicializar cliente Gemini
            self.client = genai.Client(api_key=api_key)
            self.model = "gemini-2.5-pro-preview-03-25"
            
            # Configurar o prompt base
            self.system_prompt = self._get_system_prompt()
            
            logger.info(f"Analisador de vagas inicializado com o modelo {self.model}")
        except Exception as e:
            logger.error(f"Erro ao inicializar o cliente Gemini: {str(e)}")
            raise ValueError(f"Não foi possível inicializar o cliente Gemini: {str(e)}")
    
    def _get_system_prompt(self):
        """
        Retorna o prompt do sistema que orienta o modelo sobre como analisar as vagas.
        """
        return """# CONTEXTO ESTRATÉGICO
Sua função transcende um simples ATS Reverso. Você atuará como um avaliador estratégico, aplicando um olhar crítico e experiente para dissecar a aderência do perfil do João às vagas apresentadas. O objetivo não é apenas encontrar \"matches\" superficiais, mas sim realizar uma análise de fit estratégico e identificar gaps concretos que precisam ser endereçados. Pense como um COO avaliando um candidato interno para uma posição chave: queremos substância, não apenas keywords.
-Análise de qualificações: Verifique formação acadêmica e certificações
-Cálculo de aderência global: Média ponderada das análises anteriores (10% palavras-chave, 30% requisitos, 30% experiência, 30% qualificações)
-Análise detalhada de forças e fraquezas (SWOT só com SW, sem OT)

#OUTPUT ESTRUTURADO NESTA ORDEM
-nota palavras-chave
-nota requisitos
-nota experiência
-nota qualificações
-nota global
-forças (use quebra de pagina entre os topicos)
-fraquezas (use quebra de pagina entre os topicos)

#CURRICULO
JOÃO MELLO               joaohlmello@gmail.com | Linkedin: joaohlmello | (21) 96947-1930 | São Paulo - SP

SUMÁRIO
Gerente de projetos e processos sênior com 10 anos de experiência (6 liderando) na gestão de projetos e processos de tecnologia, corporativos e de CAPEX, utilizando metodologias lean, ágeis, preditivas e Inteligência Artificial. Histórico comprovado em: Gestão de portfólios complexos (R$100MM+); Liderança de equipes multifuncionais diretas (20+) e indiretas (300+); Gestão estratégica de clientes e stakeholders; Modelagem e implementação de processos; Desenvolvimento d ...[Truncated]


EXPERIÊNCIA
SYNERGIA CONSULTORIA SOCIOAMBIENTAL (Cliente Vale)
Nov 22 – Dez 24: Diretor de Projetos de Tecnologia e Planejamento
Ago 22 – Out 22: Consultor Estratégico
Liderança executiva de projetos estratégicos e de equipe multifuncional de 20 pessoas, responsável por tecnologia, planejamento e qualidade, em uma consultoria de São Paulo com 500 funcionários e clientes como Vale e Brasken. Experiência global, no sentido de reportar trimestralmente ao CEO do fundo de private equity na Bélgica (TPF).

Gestão de Stakeholders e Crises: Liderança do turnaround do maior projeto da empresa (R$100MM, 300 pessoas), com gestão da mudança, incluindo: comunicação proativa com o cliente, alinhando expectativas e realizando entregas menores, e o replanejamento de escopo, prazo, orçamento e estrutura organizacional.

Gestão de Projetos Estratégicos: Implementação de OKR como metodologia de planejamento estratégico da empresa, integrando 90 projetos a 15 objetivos estratégicos e 3 diretrizes. Condução de ritos com a alta gestão, assegurando visibilidade e alinhamento. Planejamento e  monitoramento com as equipes executoras.

Análise de Dados e Modelagem de Processos: Desenvolvimento e implementação de sistema de gestão para acompanhamento de milhões de produtos, através do mapeamento e integração de centenas de etapas do processo, incluindo o monitoramento de KPIs e dashboards em tempo real, e automações com IA


Gestão da Qualidade: Aprovação de políticas e diretrizes corporativas, manutenção da certificação ISO através do desenvolvimento de sistema de gestão da conformidade, estabelecimento de padrões, coordenação de auditorias internas e externas, e implementação de melhoria contínua com foco no cliente e gestão de riscos.

Gestão de Produtos Digitais: Implementação de uma cultura de produto, utilizando discovery, user journey map, PRDs (product requirement documents), storys com critério de aceite, e sprints de delivery e review. Liderança executiva do desenvolvimento, com foco na jornada do cliente e eficiência operacional
Gerenciamento de Custos: Gestão do orçamento da diretoria (R$3MM) e negociação de contratos, com redução de até 40%, assegurando a viabilidade do nosso principal projeto interno.
Gestão de Produtos Digitais: Implementação de uma cultura de produto, utilizando discovery, PRDs (product requirement documents), storys com critério de aceite, e sprints de delivery e review.
Commercial Support: Supported commercial initiatives, through implementing a detailed CRM system, and helping improve the commercial processes along the way. Also supported in proposals and bids.
 
JM GESTÃO & TECNOLOGIA (Cliente Oncoclínicas)
Fev 21 – Out 22: Consultor de Processos e Projetos & Fundador
Empreendendo em consultoria de gerenciamento de projetos e processos de PMO, e tendo Oncoclínicas como cliente. Gerenciamento de R$18MM em 4 projetos de CAPEX, e desenvolvimento de sistemas de gestão de PMO.

Gestão de Projetos Complexos: Coordenação de equipes multidisciplinares (internas, cliente e terceiros)) em projetos complexos, que envolvem engenharia, tecnologia, suprimentos, operações e regulatório, aplicando metodologias estruturadas, como: estrutura analítica do projeto (EAP) - work breakdown structure (WBS), caminho crítico - critical path method (CPM) e valor agregado -  earned value management (EVM). 

Implementação de Processos de PMO: Padronização da EAP, cronogramas e curvas S para equalização do acompanhamento físico-financeiro, implementação de processos de gestão da mudança e aprovação de pleitos aditivos. Implementação do gerenciamento de riscos, resultando em zero ocorrências não mapeadas. Mapeamento, análise, definição de respostas e monitoramento contínuo. Adoção como procedimento padrão.

Transformação Digital: Desenvolvimento de sistema de ERP de contratos e custos, que se tornou diferencial contra players maiores, gerando economia global de R$700k e otimizando processos significativamente.

Planos de Treinamento: Desenvolvimento e execução de planos de treinamento de sistemas e de transição para operação. Documentação de data book completo, assegurando histórico e capacitação da equipe.
Gestão de Stakeholders: Estratégia de comunicação adaptada a cada interlocutor, do fornecedor ao sócio, apoiado por robusto processo de documentação de requisitos e gerenciamento de mudanças.
Operação assistida: Desenvolvimento e execução de planos de treinamento e transição para operação. Documentação de data book completo, assegurando histórico e capacitação da equipe.

EQSEED
Out 20 – Jul 21: Head de Projetos e Operações & Sócio
Fev 20 – Set 20: Especialista em Gestão de Projetos e Processos
Respondendo ao CEO inglês, e responsável por projetos de transformação digital e operações em uma startup fintech com 20 funcionários. Marketplace de investimentos em  venture capital para o mercado financeiro.
Liderança Multifuncional: Promoção de especialista para head em oito meses. Gestão do time de Operações após a saída do COO (4 pessoas), responsável pelas áreas funcionais de  finanças, contabilidade, TI e RH.

Gestão de Projetos Ágeis: Implementação de metodologias ágeis (OKRs e Kanban) para toda a empresa, principalmente tecnologia, marketing e comercial, dando visibilidade de todas as atividades e iniciativas, e viabilizando uma priorização integrada dos roadmaps de projetos com a necessidade do negócio

Transformação Digital de Processos: Automação do batimento financeiro, reduzindo o lead time em 80%. Sistematização da análise de investimentos, aumentando a produtividade em 6x. Monitoramento da interação dos usuários com a plataforma, viabilizando a gestão do funil de vendas e aumentando a conversão de leads em 15%. Automação dos processos de pós vendas, aumentando NPS para a zona de Excelência.

Gestão Financeira: Gerenciamento do Runway (tempo até a falência por falta de caixa) durante o COVID-19, incluindo a renegociação de todos os contratos e fluxo de caixa descontado por cenários.

CARGOS ANTERIORES
Abr 18 – Ago 19: N&A CONSULTORES (brMalls) – Coordenador de Planejamento e Controle de Projetos
Ago 17 – Mar 18: N&A CONSULTORES (brMalls) – Analista de Planejamento e Controle de Projetos
Nov 16 – Ago 17: ONCOCLÍNICAS – Estagiário de PMO
Jul 15 – Jun 16: N&A CONSULTORES (brMalls) – Estagiário de Planejamento e Controle de Projetos
Jan 14 – Jan 15: MÉTODO ENGENHARIA – Estagiário de Planejamento e Controle de Projetos

EDUCAÇÃO E CERTIFICAÇÕES
MBA em Gerenciamento de Projetos  – Fundação Getúlio Vargas (FGV) – Concluído
Graduação em Engenharia – Estácio – Concluído
Certificação Project Management Professional (PMP) – Project Management Institute (PMI) – 2020
Certificação Scrum Foundations Professional Certificate (SFPC) – Certiprof – 2020
Certificação Lean Six Sigma Green Belt – Advanced Innovation Group Pro Excellence (AIGPE) – 2020

CONHECIMENTOS
Idiomas: Inglês fluente;
Metodologias e Frameworks: PMBOK, Waterfall/Preditiva/Tradicional, Agile, Scrum, Kanban, Lean;
Sistemas de Gestão: Ms Project, JIRA, Confluence, Azure Devops, Pipefy;
ERP: Totvs, Oracle;
Dados: Power BI, Google Data Studio, Metabase, SQL, Python;
Desenvolvimento: Low code, Python, Replit, N8N, Glide, Power Apps, Powe Automate;
Inteligência Artificial (AI): API OpenAI e API Gemini;
Essenciais: Excel Avançado, PowerPoint."""
    
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
            
            # Limpar a descrição da vaga para remover tags HTML
            clean_description = job_description.replace('<br><br>', '\n\n').replace('<br>', '\n')
            
            # Construir o prompt do usuário para análise
            user_prompt = f"""
# VAGA: {job_title}
# EMPRESA: {company_name}

# DESCRIÇÃO DA VAGA:
{clean_description}

Analisar a compatibilidade entre o currículo do candidato (fornecido no seu contexto) e esta vaga de emprego.
            """
            
            # Configurar a resposta esperada no formato JSON
            generate_content_config = types.GenerateContentConfig(
                temperature=0.65,
                response_mime_type="application/json",
                response_schema=genai.types.Schema(
                    type=genai.types.Type.OBJECT,
                    required=["nota_palavras_chave", "nota_requisitos", "nota_experiencia", 
                             "nota_qualificacoes", "nota_global", "forcas", "fraquezas"],
                    properties={
                        "nota_palavras_chave": genai.types.Schema(
                            type=genai.types.Type.INTEGER,
                        ),
                        "nota_requisitos": genai.types.Schema(
                            type=genai.types.Type.INTEGER,
                        ),
                        "nota_experiencia": genai.types.Schema(
                            type=genai.types.Type.INTEGER,
                        ),
                        "nota_qualificacoes": genai.types.Schema(
                            type=genai.types.Type.INTEGER,
                        ),
                        "nota_global": genai.types.Schema(
                            type=genai.types.Type.INTEGER,
                        ),
                        "forcas": genai.types.Schema(
                            type=genai.types.Type.STRING,
                        ),
                        "fraquezas": genai.types.Schema(
                            type=genai.types.Type.STRING,
                        ),
                    },
                ),
            )
            
            # Fazer a chamada à API do Gemini
            logger.info(f"Enviando solicitação de análise para vaga: {job_title}")
            
            try:
                # Criar conteúdo para enviar ao modelo
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=user_prompt),
                        ],
                    ),
                ]
                
                # Adicionar instruções do sistema
                system_instruction = [
                    types.Part.from_text(text=self.system_prompt),
                ]
                
                # Fazer a chamada ao modelo
                response = self.client.generate_content(
                    model=self.model,
                    contents=contents,
                    config=generate_content_config,
                    system_instruction=system_instruction,
                )
                
                # Obter a resposta
                if response and hasattr(response, 'text'):
                    # A API mais recente retorna o texto diretamente
                    result_json = response.text
                else:
                    logger.error("Resposta inválida do Gemini API")
                    return {
                        "error": "Formato de resposta inválido da API do Gemini",
                        "raw_response": str(response)
                    }
                
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
                    
                    # Adicionar informações da vaga ao resultado
                    analysis_data['job_title'] = job_title
                    analysis_data['company_name'] = company_name
                    analysis_data['job_link'] = job_data.get('link', '')
                    
                    logger.info(f"Análise concluída para vaga: {job_title} - Nota global: {analysis_data.get('nota_global', 'N/A')}")
                    return analysis_data
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Erro ao decodificar JSON do resultado: {e}")
                    return {
                        "error": f"Formato de resposta inválido: {e}",
                        "raw_response": result_json
                    }
            else:
                logger.error("Resposta vazia ou sem texto do Gemini API")
                return {
                    "error": "Resposta vazia da API do Gemini",
                    "raw_response": str(response) if response else "Nenhuma resposta"
                }
                
        except Exception as e:
            logger.error(f"Erro ao analisar vaga: {str(e)}")
            return {
                "error": f"Erro na análise: {str(e)}"
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
        
        # Inicializar progresso
        if progress_callback:
            progress_callback(0, total_jobs, "Iniciando análise de compatibilidade...")
        
        for i, job in enumerate(jobs_data):
            job_title = job.get('job_title', 'Desconhecido')
            logger.info(f"Analisando vaga {i+1}/{total_jobs}: {job_title}")
            
            # Atualizar progresso
            if progress_callback:
                progress_callback(i, total_jobs, f"Analisando vaga {i+1}/{total_jobs}: {job_title}")
            
            # Implementar retry com backoff exponencial
            retry_count = 0
            success = False
            result = {"error": "Não foi possível analisar a vaga após tentativas"}
            
            while not success and retry_count < max_retries:
                try:
                    if retry_count > 0:
                        # Aumentar tempo de espera entre tentativas e usar backoff exponencial
                        # Base de 5 segundos com fator exponencial para cada tentativa
                        wait_time = 5 * (2 ** (retry_count - 1))
                        logger.info(f"Tentativa {retry_count+1}/{max_retries} - Aguardando {wait_time}s antes de tentar novamente")
                        
                        # Atualizar progresso se houver retry
                        if progress_callback:
                            progress_callback(
                                i, 
                                total_jobs, 
                                f"Vaga {i+1}/{total_jobs}: Tentativa {retry_count+1}/{max_retries} em {wait_time}s..."
                            )
                            
                        # Dormir pelo tempo calculado
                        time.sleep(wait_time)
                    
                    # Analisar a vaga
                    result = self.analyze_job(job)
                    
                    # Verificar se a análise foi bem-sucedida
                    if "error" not in result:
                        success = True
                    else:
                        logger.warning(f"Erro na tentativa {retry_count+1}: {result.get('error')}")
                        retry_count += 1
                        
                except Exception as e:
                    logger.error(f"Exceção na tentativa {retry_count+1}: {str(e)}")
                    retry_count += 1
            
            # Adicionar resultado à lista
            results.append(result)
            
            # Atualizar progresso após completar a vaga
            if progress_callback:
                progress_callback(
                    i + 1, 
                    total_jobs, 
                    f"Vaga {i+1}/{total_jobs} concluída: {job_title}"
                )
            
            # Aguardar entre chamadas para evitar limites de API
            if i < len(jobs_data) - 1:
                time.sleep(delay_between_calls)
        
        # Finalizar progresso
        if progress_callback:
            progress_callback(total_jobs, total_jobs, "Análise de todas as vagas concluída!")
            
        return results


# Função auxiliar para transformar a análise em HTML
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
        
    formatted = text.replace("\n\n", "<br><br>").replace("\n", "<br>")
    return formatted


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
            <h4>Erro na análise</h4>
            <p>{analysis['error']}</p>
        </div>
        """
    
    # Formatar os detalhes da análise
    html = f"""
    <div class="job-analysis card">
        <div class="card-header bg-dark text-white">
            <h4>{analysis.get('job_title', 'Vaga')} - {analysis.get('company_name', '')}</h4>
            <p><a href="{analysis.get('job_link', '#')}" target="_blank">{analysis.get('job_link', '')}</a></p>
        </div>
        <div class="card-body">
            <div class="row mb-4">
                <div class="col">
                    <div class="analysis-score-container">
                        <div class="analysis-score-circle" style="--score: {analysis.get('nota_global', 0)}%;">
                            <span class="analysis-score-text">{analysis.get('nota_global', 0)}%</span>
                        </div>
                        <div class="analysis-score-label">Compatibilidade Global</div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-md-3">
                    <div class="analysis-details-card">
                        <h5>Palavras-chave</h5>
                        <div class="progress">
                            <div class="progress-bar bg-info" role="progressbar" style="width: {analysis.get('nota_palavras_chave', 0)}%;" 
                                aria-valuenow="{analysis.get('nota_palavras_chave', 0)}" aria-valuemin="0" aria-valuemax="100">
                                {analysis.get('nota_palavras_chave', 0)}%
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-details-card">
                        <h5>Requisitos</h5>
                        <div class="progress">
                            <div class="progress-bar bg-info" role="progressbar" style="width: {analysis.get('nota_requisitos', 0)}%;" 
                                aria-valuenow="{analysis.get('nota_requisitos', 0)}" aria-valuemin="0" aria-valuemax="100">
                                {analysis.get('nota_requisitos', 0)}%
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-details-card">
                        <h5>Experiência</h5>
                        <div class="progress">
                            <div class="progress-bar bg-info" role="progressbar" style="width: {analysis.get('nota_experiencia', 0)}%;" 
                                aria-valuenow="{analysis.get('nota_experiencia', 0)}" aria-valuemin="0" aria-valuemax="100">
                                {analysis.get('nota_experiencia', 0)}%
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-details-card">
                        <h5>Qualificações</h5>
                        <div class="progress">
                            <div class="progress-bar bg-info" role="progressbar" style="width: {analysis.get('nota_qualificacoes', 0)}%;" 
                                aria-valuenow="{analysis.get('nota_qualificacoes', 0)}" aria-valuemin="0" aria-valuemax="100">
                                {analysis.get('nota_qualificacoes', 0)}%
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="strengths-card">
                        <h5>Forças</h5>
                        <div class="strengths-content">
                            {format_text_with_breaks(analysis.get('forcas', ''))}
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="weaknesses-card">
                        <h5>Fraquezas</h5>
                        <div class="weaknesses-content">
                            {format_text_with_breaks(analysis.get('fraquezas', ''))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    
    return html