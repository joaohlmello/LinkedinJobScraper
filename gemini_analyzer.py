import os
import json
import logging
import time
import google.generativeai as genai

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
        
        # Inicializar cliente Gemini
        genai.configure(api_key=api_key)
        self.model_name = "gemini-pro"  # Modelo que suporta schemas
        self.model = genai.GenerativeModel(model_name=self.model_name)
        
        # Configurar o prompt base
        self.system_prompt = self._get_system_prompt()
        
        logger.info(f"Analisador de vagas inicializado com o modelo {self.model_name}")
    
    def _get_system_prompt(self):
        """
        Retorna o prompt do sistema que orienta o modelo sobre como analisar as vagas.
        """
        return """#CONTEXTO
-Você é um ATS Aplicant Tracking System reverso, que ajudará o candidato avaliar vagas de emprego e analisar o % de aderência.

#METODOLOGIA DE AVALIAÇÃO DE ADERÊNCIA
-Identificação de palavras-chave: Extraia e liste as principais palavras-chave da descrição da vaga. Considere o Contexto: Título > Descrição > Outros
-Análise de requisitos: Avalie cada requisito individualmente, atribuindo uma porcentagem de aderência
-Avaliação de experiência: Compare experiências listadas com as exigidas.
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
SUMÁRIO
Gerente de projetos sênior com 10 anos de experiência na gestão de projetos de tecnologia, corporativos e de CAPEX, utilizando metodologias ágeis e preditivas. Histórico comprovado em: Gestão de portfólios complexos (R$100MM+); Liderança de equipes multifuncionais diretas (20+) e indiretas (300+); Gestão estratégica de clientes e stakeholders; Modelagem e implementação de processos lean; Desenvolvimento de sistemas de gestão e; Análise e monitoramento de dados e KPIs ...[Truncated]



EXPERIÊNCIA
SYNERGIA CONSULTORIA SOCIOAMBIENTAL (Cliente Vale)
Nov 22 – Dez 24: Diretor de Projetos de Tecnologia e Planejamento
Ago 22 – Out 22: Consultor Estratégico
Liderança executiva de projetos estratégicos e de equipe multifuncional de 20 pessoas, responsável por tecnologia, planejamento e qualidade, em uma consultoria de São Paulo com 500 funcionários e clientes como Vale e Brasken. Experiência global, no sentido de reportar trimestralmente ao CEO do fundo de private equity na Bélgica (TPF).

Gestão de Stakeholders e Crises: Liderança do turnaround do maior projeto da empresa (R$100MM, 300 pessoas), com gestão da mudança, incluindo: comunicação proativa com o cliente, alinhando expectativas e realizando entregas menores, e o replanejamento de escopo, prazo, orçamento e estrutura organizacional.
 
Gestão de Projetos Estratégicos: Implementação de OKR como metodologia de planejamento estratégico da empresa, integrando 90 projetos a 15 objetivos estratégicos e 3 diretrizes. Condução de ritos com a alta gestão, assegurando visibilidade e alinhamento. Planejamento e  monitoramento com as equipes executoras.

Análise de Dados e Modelagem de Processos: Desenvolvimento e implementação de sistema de gestão PPM para acompanhamento de milhões de produtos, através do mapeamento e integração de centenas de etapas do processo, incluindo o monitoramento de KPIs e dashboards em tempo real para avaliação de desempenho.

Gestão da Qualidade: Aprovação de políticas e diretrizes corporativas, manutenção da certificação ISO através do desenvolvimento de sistema de gestão da conformidade, estabelecimento de padrões, coordenação de auditorias internas e externas, e implementação de melhoria contínua com foco no cliente e gestão de riscos.

JM GESTÃO & TECNOLOGIA (Cliente Oncoclínicas)
Fev 21 – Out 22: Gerente de Projetos & Fundador
Empreendendo em consultoria de gerenciamento de projetos e implantação de PMO, e tendo Oncoclínicas como cliente. Gerenciamento de R$18MM em 4 projetos de CAPEX, e desenvolvimento de sistemas de gestão de PMO.

Gestão de Projetos Complexos: Coordenação de equipes multidisciplinares (internas, cliente e terceiros)) em projetos complexos, que envolvem engenharia, tecnologia, suprimentos, operações e regulatório, aplicando metodologias estruturadas, como: estrutura analítica do projeto (EAP) - work breakdown structure (WBS), caminho crítico - critical path method (CPM) e valor agregado -  earned value management (EVM). 

Implementação de PMO: Padronização da EAP, cronogramas e curvas S para equalização do acompanhamento físico-financeiro, implementação de processos de gestão da mudança e aprovação de pleitos aditivos.

Gerenciamento de Riscos: Implementação do processo, resultando em zero ocorrências não mapeadas. Mapeamento, análise, definição de respostas e monitoramento contínuo. Adoção como procedimento padrão.

Transformação Digital: Desenvolvimento de sistema de ERP de contratos e custos, que se tornou diferencial contra players maiores, gerando economia global de R$700k e otimizando processos significativamente.

Planos de Treinamento: Desenvolvimento e execução de planos de treinamento de sistemas e de transição para operação. Documentação de data book completo, assegurando histórico e capacitação da equipe.

EQSEED
Out 20 – Jul 21: Head de Projetos e Operações & Sócio
Fev 20 – Set 20: Especialista em Gestão de Projetos
Respondendo ao CEO inglês, e responsável por projetos de transformação digital e operações em uma startup fintech com 20 funcionários. Marketplace de investimentos em  venture capital para o mercado financeiro.
Liderança Multifuncional: Promoção de especialista para head em oito meses. Gestão do time de Operações após a saída do COO (4 pessoas), responsável pelas áreas funcionais de  finanças, contabilidade, TI e RH.

Gestão de Projetos Ágeis: Implementação de metodologias ágeis (OKRs e Kanban) para toda a empresa, principalmente tecnologia, marketing e comercial, dando visibilidade de todas as atividades e iniciativas, e viabilizando uma priorização integrada dos roadmaps de projetos com a necessidade do negócio

Transformação Digital: Automação do batimento financeiro, reduzindo o lead time em 80%. Sistematização da análise de investimentos, aumentando a produtividade em 6x. Monitoramento da interação dos usuários com a plataforma, viabilizando a gestão do funil de vendas e aumentando a conversão de leads em 15%.

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

CONHECIMENTOS
Idiomas: Inglês fluente;
Metodologias e Frameworks: PMBOK, Waterfall, Scrum, Kanban;
Sistemas de Gestão: Ms Project, JIRA, Confluence, Azure Devops;
ERP: Totvs, Oracle;
Dados: Power BI, Google Data Studio, Metabase, SQL, Python;
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
            
            # Construir o prompt de usuário
            user_prompt = f"""
# VAGA: {job_title}
# EMPRESA: {company_name}

# DESCRIÇÃO DA VAGA:
{clean_description}

Analisar a compatibilidade entre o currículo do candidato (fornecido no seu contexto) e esta vaga de emprego.
"""
            
            # Configurar o esquema de resposta usando dicionário JSON padrão
            response_schema = {
                "type": "object",
                "required": ["nota_palavras_chave", "nota_requisitos", "nota_experiencia", 
                          "nota_qualificacoes", "nota_global", "forcas", "fraquezas"],
                "properties": {
                    "nota_palavras_chave": {
                        "type": "integer"
                    },
                    "nota_requisitos": {
                        "type": "integer"
                    },
                    "nota_experiencia": {
                        "type": "integer"
                    },
                    "nota_qualificacoes": {
                        "type": "integer"
                    },
                    "nota_global": {
                        "type": "integer"
                    },
                    "forcas": {
                        "type": "string"
                    },
                    "fraquezas": {
                        "type": "string"
                    }
                }
            }
            
            # Configurar as configurações de segurança
            safety_settings = [
                genai.types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="BLOCK_NONE",
                ),
                genai.types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_NONE",
                ),
                genai.types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="BLOCK_NONE",
                ),
                genai.types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_NONE",
                ),
            ]
            
            # Criar o conteúdo da solicitação
            contents = [
                genai.types.Content(
                    role="system",
                    parts=[genai.types.Part.from_text(text=self.system_prompt)],
                ),
                genai.types.Content(
                    role="user",
                    parts=[genai.types.Part.from_text(text=user_prompt)],
                ),
            ]
            
            # Configuração da geração
            generation_config = genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            )
            
            # Fazer a chamada à API
            logger.info(f"Enviando solicitação de análise para vaga: {job_title}")
            
            try:
                # Usar diretamente o modelo GenerativeModel
                result = self.model.generate_content(
                    contents=contents,
                    generation_config=generation_config,
                )
            except Exception as e:
                logger.error(f"Erro na chamada à API do Gemini: {str(e)}")
                raise Exception(f"Falha na análise com Gemini API: {str(e)}")
            
            # Analisar e retornar o resultado
            if result and hasattr(result, 'text'):
                try:
                    # Processar o resultado como JSON
                    analysis_data = json.loads(result.text)
                    
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
                        "raw_response": result.text
                    }
            else:
                logger.error("Resposta vazia ou sem texto do Gemini API")
                return {
                    "error": "Resposta vazia da API do Gemini",
                    "raw_response": str(result) if result else "Nenhuma resposta"
                }
                
        except Exception as e:
            logger.error(f"Erro ao analisar vaga: {str(e)}")
            return {
                "error": f"Erro na análise: {str(e)}"
            }
    
    def analyze_jobs_batch(self, jobs_data, max_retries=3, delay_between_calls=2, progress_callback=None):
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
                        # Espera exponencial em caso de retry
                        wait_time = delay_between_calls * (2 ** (retry_count - 1))
                        logger.info(f"Tentativa {retry_count+1}/{max_retries} - Aguardando {wait_time}s")
                        
                        # Atualizar progresso se houver retry
                        if progress_callback:
                            progress_callback(
                                i, 
                                total_jobs, 
                                f"Vaga {i+1}/{total_jobs}: Tentativa {retry_count+1}/{max_retries}..."
                            )
                            
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