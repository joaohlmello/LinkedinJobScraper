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
            # Inicializar cliente Gemini
            self.client = genai.Client(api_key=api_key)
            self.model_name = "gemini-2.5-flash-preview-04-17"
            
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
        return """# 1. CONTEXTO ESTRATÉGICO
Pense como um Diretor de RH avaliando um candidato externo para uma posição chave e que recebe centenas de currículos. Você precisa tomar uma decisão de contratação com base em fatos e evidências, não em otimismo.

# 2. METODOLOGIA DE AVALIAÇÃO
Para o currículo A
-Cargos Anteriores Currículo A: Avalie a trajetória profissional e compatibilidade de cargos anteriores e responsabilidades anteriores. Dê peso maior ao cargo mais recente. Seja crítico.
-Cargos Anteriores Currículo B.
-Requisitos (igual para Curriculum A e B: Disseque cada requisito explícito. Atribua uma nota binária de aderência (0 ou 1) justificada para cada um.
-Cálculo de Aderência Ponderada: Separadamente para cada currículo: 40% cargos anteriores, 60%.
-Forças: Identifique e liste as forças reais do profissional que representam um diferencial específico para esta vaga.
-Fraquezas: Identifique e liste as fraquezas reais do profissional que representam um problema específico para esta vaga. Inclua pontos que podem gerar questionamentos ou exigirão justificativa. Sem eufemismos.

# 6. ESTRUTURA DO OUTPUT
Exatamente nesta ordem
## IDIOMA
- Idioma da vaga (portugues OU ingles)
## CURRICULO A
- Notas cargos anteriores
- Nota requisitos
- Nota final
## CURRICULO B
- Notas cargos anteriores
- Nota requisitos
- Nota final
## SW
- Forças
- Fraquezas





#CURRICULOS (A UNICA DIFERENÇA ENTRE AS VERSÕES É O TITULO DOS CARGOS) 
JOÃO MELLO                           joaohlmello@gmail.com | Linkedin: joaohlmello | (21) 96947-1930 | São Paulo - SP

SUMÁRIO
Gerente de Projetos, Produto e Operações com 10 anos de experiência (7 em posições de liderança).


EXPERIÊNCIA
SYNERGIA CONSULTORIA (Cliente VALE) 
Nov/22 - Dez/24: Head de Planejamento e Projetos de Tecnologia (curriculo 0) // Head de Planejamento e Projetos de Tecnologia (curriculo A) // Head de Panejamento e Produtos de Tecnologia (curriculo B)
Liderança executiva de projetos e áreas de Planejamento, Produtos Digitais, Desenvolvimento e Dados em Consultoria (600 pessoas). Equipe multifuncional de 17 pessoas, Reporte aos CEOs Brasil e do fundo de private equity (TPF - Bélgica).

Estruturação da Diretoria: Defini estratégia, organograma e processos, viabilizando ~R$20MM em novos negócios.
Gestão de Stakeholders e Crises: Liderei o turnaround do maior contrato da empresa (R$100MM), reestruturando escopo, prazo e orçamento, resultando na recuperação da confiança do cliente e adequação à nova meta em 6 meses.
Gestão do Planejamento Estratégico: Implementei OKR para toda a empresa, integrando 90 projetos internos a 15 objetivos estratégicos, engajando a alta gestão e aumentando o atingimento de ~50% para ~85% em 1 ano.
Gestão de Projetos de Tecnologia (Produtos): Remodelei a fábrica de software para squads ágeis com práticas de Product Management (discovery, PRDs, stories, sprints), melhorando significativamente o alinhamento das entregas com as necessidades do negócio e gerando novas linhas de faturamento. Destaco os Projetos (Produtos):
PMOs Data-driven: Sistemas de gestão para monitoramento de milhões de produtos em centenas de etapas, com regras de negócio complexas e entregas via API, reduzindo o tempo de reporte de 1 semana para em tempo real.
Reconstrução de Sistema Legado: Coleta e análise de dados de mercado com integração offline to online (O2O), corrigindo problemas de UI, UX, bugs recorrentes, extração de dados e integrações.
Gerador de Documentos com IA: Geração automatizada de laudos e pareceres com integrações com bancos de dados, APIs e inteligência artificial com human in the loop, viabilizando contrato com a redução de custo e prazo.
 
JM GESTÃO & TECNOLOGIA (Cliente ONCOCLÍNICAS)
Jul/21 - Out/22: Fundador (currículo 0) // Fundador, Gerente de Projetos e Consultor de PMO (currículo A) // Fundador e Product Builder (currículo B)
Tech startup de consultoria focada em gerenciamento de projetos, comigo e 2 funcionários (PMO e Dev).

Gestão de Projetos: Gerenciei portfólio de 4 projetos de CAPEX (R$18MM), coordenando equipes e aplicando metodologias para assegurar escopo, prazo e orçamento, alcançando nota máxima na avaliação de fornecedores.
Implementação de Processos e PMO: Defini e padronizei EAPs, cronogramas, curvas S, gestão da mudança e riscos, resultando em maior previsibilidade, zero mudanças não mapeadas de escopo zero ocorrências críticas não mapeadas.
Transformação Digital (Produto): Liderei o desenvolvimento de sistema ERP com inteligência artificial, gerando economia direta de R$700K, reduzindo o tempo de aprovação de 7 dias para 3, e as não conformidades em ~95%.

EQSEED
Fev/20 - Jul/21: Líder de Projetos e Produtos (currículo 0) // Líder de Projetos e Operações (currículo A) // Líder de Produtos (currículo B)
Liderança de produto e projetos de transformação digital em startup do mercado financeiro (marketplace de venture capital, 20 funcionários), reportando ao CEO inglês e ao CSO americano. Promovido a equity partner em 8 meses.

Gestão Ágil: Implementei OKRs e Kanban em toda a empresa (Tecnologia, Negócios, Marketing e Vendas), unindo o tático com o estratégico, elevando a transparência e viabilizando a priorização integrada do roadmap.
Gestão de Projetos (Produtos): Liderei o produto e projetos de transformação digital do discovery ao deploy. Destaco:
Monitoramento do CRM / funil de vendas e carrinho abandonado (aumento de 15% na conversão);
Automação do pós-vendas (NPS elevado à Zona de Excelência >75);
Automação do batimento financeiro (redução de ~80% no lead time);
Modelagem e sistematização da análise de investimentos (produtividade 6x maior);
Modelagem e sistematização do cálculo de valuation do portfólio (redução de 2 dias de trabalho).
Gestão de Operações: Assumi a gestão interina do time de Ops (4 pessoas) após saída do COO. Gerenciei o runway (tempo de caixa) durante a crise da COVID-19, liderando a renegociação de contratos e modelagem de cenários.

CARGOS ANTERIORES
Abr/18 - Ago/19: N&A CONSULTORES (Cliente BRMALLS) - Coordenador de Planejamento e Controle de Projetos
Ago/17 - Mar/18: N&A CONSULTORES (Cliente BRMALLS) - Analista de Planejamento e Controle de Projetos
Nov/16 - Ago/17: ONCOCLÍNICAS - Estagiário de PMO
Jul/15 - Jun/16: N&A CONSULTORES (Cliente BRMALLS) - Estagiário de Planejamento e Controle de Projetos
Jan/14 - Jan/15: MÉTODO ENGENHARIA - Estagiário de Planejamento e Controle de Projetos

EDUCAÇÃO E CERTIFICAÇÕES
MBA em Gerenciamento de Projetos - Fundação Getúlio Vargas (FGV) - Concluído
Bacharelado em Engenharia - Estácio - Concluído
Certificação Project Management Professional (PMP) - Project Management Institute (PMI) - 2020
Certificação Scrum Foundations Professional Certificate (SFPC) - Certiprof - 2020

CONHECIMENTOS
Idiomas: Inglês Fluente (C1).
Metodologias e Frameworks de Projeto: PMBOK (Waterfall / Preditiva), Agile (Scrum, Kanban), Lean Six Sigma, BPMN.
Metodologias e Frameworks de Produto: OKR, Design Thinking.
Análise de Dados e BI: Power BI, Metabase, SQL (consultas SELECT, JOINs, agregações).
RPA e Low-code: Python (scripts e automações vibe code), Power Automate, Power Apps, N8N, Glide. 
Inteligência Artificial: APIs OpenAI e Gemini.
Softwares de Gestão e CRM: MS Project, Jira, Confluence, Azure DevOps, Notion, Asana, Trello, Pipefy, Pipedrive.
Softwares de Design e Colaboração: Miro, Mural.
Softwares de Serviços e ERPs: Fluig, ServiceNow, TOTVS Protheus, Oracle EBS.
Essenciais: Pacote Office Avançado (Excel, PowerPoint, etc.)."""[Truncated]


EXPERIÊNCIA
SYNERGIA CONSULTORIA SOCIOAMBIENTAL (Cliente Vale)
Nov 22 - Dez 24: Diretor de Projetos de Tecnologia e Planejamento
Ago 22 - Out 22: Consultor Estratégico
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
Fev 21 - Out 22: Consultor de Processos e Projetos & Fundador
Empreendendo em consultoria de gerenciamento de projetos e processos de PMO, e tendo Oncoclínicas como cliente. Gerenciamento de R$18MM em 4 projetos de CAPEX, e desenvolvimento de sistemas de gestão de PMO.

Gestão de Projetos Complexos: Coordenação de equipes multidisciplinares (internas, cliente e terceiros)) em projetos complexos, que envolvem engenharia, tecnologia, suprimentos, operações e regulatório, aplicando metodologias estruturadas, como: estrutura analítica do projeto (EAP) - work breakdown structure (WBS), caminho crítico - critical path method (CPM) e valor agregado -  earned value management (EVM). 

Implementação de Processos de PMO: Padronização da EAP, cronogramas e curvas S para equalização do acompanhamento físico-financeiro, implementação de processos de gestão da mudança e aprovação de pleitos aditivos. Implementação do gerenciamento de riscos, resultando em zero ocorrências não mapeadas. Mapeamento, análise, definição de respostas e monitoramento contínuo. Adoção como procedimento padrão.

Transformação Digital: Desenvolvimento de sistema de ERP de contratos e custos, que se tornou diferencial contra players maiores, gerando economia global de R$700k e otimizando processos significativamente.

Planos de Treinamento: Desenvolvimento e execução de planos de treinamento de sistemas e de transição para operação. Documentação de data book completo, assegurando histórico e capacitação da equipe.
Gestão de Stakeholders: Estratégia de comunicação adaptada a cada interlocutor, do fornecedor ao sócio, apoiado por robusto processo de documentação de requisitos e gerenciamento de mudanças.
Operação assistida: Desenvolvimento e execução de planos de treinamento e transição para operação. Documentação de data book completo, assegurando histórico e capacitação da equipe.

EQSEED
Out 20 - Jul 21: Head de Projetos e Operações & Sócio
Fev 20 - Set 20: Especialista em Gestão de Projetos e Processos
Respondendo ao CEO inglês, e responsável por projetos de transformação digital e operações em uma startup fintech com 20 funcionários. Marketplace de investimentos em  venture capital para o mercado financeiro.
Liderança Multifuncional: Promoção de especialista para head em oito meses. Gestão do time de Operações após a saída do COO (4 pessoas), responsável pelas áreas funcionais de  finanças, contabilidade, TI e RH.

Gestão de Projetos Ágeis: Implementação de metodologias ágeis (OKRs e Kanban) para toda a empresa, principalmente tecnologia, marketing e comercial, dando visibilidade de todas as atividades e iniciativas, e viabilizando uma priorização integrada dos roadmaps de projetos com a necessidade do negócio

Transformação Digital de Processos: Automação do batimento financeiro, reduzindo o lead time em 80%. Sistematização da análise de investimentos, aumentando a produtividade em 6x. Monitoramento da interação dos usuários com a plataforma, viabilizando a gestão do funil de vendas e aumentando a conversão de leads em 15%. Automação dos processos de pós vendas, aumentando NPS para a zona de Excelência.

Gestão Financeira: Gerenciamento do Runway (tempo até a falência por falta de caixa) durante o COVID-19, incluindo a renegociação de todos os contratos e fluxo de caixa descontado por cenários.

CARGOS ANTERIORES
Abr 18 - Ago 19: N&A CONSULTORES (brMalls) - Coordenador de Planejamento e Controle de Projetos
Ago 17 - Mar 18: N&A CONSULTORES (brMalls) - Analista de Planejamento e Controle de Projetos
Nov 16 - Ago 17: ONCOCLÍNICAS - Estagiário de PMO
Jul 15 - Jun 16: N&A CONSULTORES (brMalls) - Estagiário de Planejamento e Controle de Projetos
Jan 14 - Jan 15: MÉTODO ENGENHARIA - Estagiário de Planejamento e Controle de Projetos

EDUCAÇÃO E CERTIFICAÇÕES
MBA em Gerenciamento de Projetos  - Fundação Getúlio Vargas (FGV) - Concluído
Graduação em Engenharia - Estácio - Concluído
Certificação Project Management Professional (PMP) - Project Management Institute (PMI) - 2020
Certificação Scrum Foundations Professional Certificate (SFPC) - Certiprof - 2020
Certificação Lean Six Sigma Green Belt - Advanced Innovation Group Pro Excellence (AIGPE) - 2020

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
            input_text = f"""
# VAGA: {job_title}
# EMPRESA: {company_name}

# DESCRIÇÃO DA VAGA:
{clean_description}

Analisar a compatibilidade entre o currículo do candidato (fornecido no seu contexto) e esta vaga de emprego.
            """
            
            # Configuração do schema de resposta esperado com novos campos
            schema = types.Schema(
                type=types.Type.OBJECT,
                required=["idioma", "forcas", "fraquezas", "nota_requisitos", "nota_cargos_a", "nota_cargos_b", "nota_final_a", "nota_final_b"],
                properties={
                    "idioma": types.Schema(type=types.Type.STRING),
                    "forcas": types.Schema(type=types.Type.STRING),
                    "fraquezas": types.Schema(type=types.Type.STRING),
                    "nota_requisitos": types.Schema(type=types.Type.NUMBER),
                    "nota_cargos_a": types.Schema(type=types.Type.NUMBER),
                    "nota_cargos_b": types.Schema(type=types.Type.NUMBER),
                    "nota_final_a": types.Schema(type=types.Type.NUMBER),
                    "nota_final_b": types.Schema(type=types.Type.NUMBER),
                }
            )
            
            # Configuração da geração
            generate_content_config = types.GenerateContentConfig(
                temperature=0.65,
                response_mime_type="application/json",
                response_schema=schema,
                system_instruction=[
                    types.Part.from_text(text=self.system_prompt)
                ]
            )
            
            # Conteúdo para a requisição
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=input_text),
                    ],
                ),
            ]
            
            # Fazer a chamada à API do Gemini
            logger.info(f"Enviando solicitação de análise para vaga: {job_title}")
            
            try:
                # Fazer a chamada ao modelo
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=generate_content_config,
                )
                
                # Obter a resposta como JSON
                result_json = response.text
                
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
                    
                    logger.info(f"Análise concluída para vaga: {job_title} - Compatibilidade A: {analysis_data.get('nota_final_a', 'N/A')}%, Compatibilidade B: {analysis_data.get('nota_final_b', 'N/A')}%")
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
    
    # Formatar os detalhes da análise com os novos campos
    html = f"""
    <div class="job-analysis card">
        <div class="card-header bg-dark text-white">
            <h4>{analysis.get('job_title', 'Vaga')} - {analysis.get('company_name', '')}</h4>
            <p><a href="{analysis.get('job_link', '#')}" target="_blank">{analysis.get('job_link', '')}</a></p>
        </div>
        <div class="card-body">
            <div class="row mb-3">
                <div class="col-md-12">
                    <div class="analysis-details-card">
                        <h5>Idioma</h5>
                        <p>{analysis.get('idioma', 'Não informado')}</p>
                    </div>
                </div>
            </div>
            
            <div class="row mb-4">
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
                        <h5>Cargo A</h5>
                        <div class="progress">
                            <div class="progress-bar bg-info" role="progressbar" style="width: {analysis.get('nota_cargos_a', 0)}%;" 
                                aria-valuenow="{analysis.get('nota_cargos_a', 0)}" aria-valuemin="0" aria-valuemax="100">
                                {analysis.get('nota_cargos_a', 0)}%
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-details-card">
                        <h5>Cargo B</h5>
                        <div class="progress">
                            <div class="progress-bar bg-info" role="progressbar" style="width: {analysis.get('nota_cargos_b', 0)}%;" 
                                aria-valuenow="{analysis.get('nota_cargos_b', 0)}" aria-valuemin="0" aria-valuemax="100">
                                {analysis.get('nota_cargos_b', 0)}%
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-score-container">
                        <div class="analysis-score-circle" style="--score: {analysis.get('nota_final_a', 0)}%;">
                            <span class="analysis-score-text">{analysis.get('nota_final_a', 0)}%</span>
                        </div>
                        <div class="analysis-score-label">Compatibilidade A</div>
                    </div>
                </div>
            </div>
            
            <div class="row mb-4">
                <div class="col-md-12 text-center">
                    <div class="analysis-score-container" style="display: inline-block;">
                        <div class="analysis-score-circle" style="--score: {analysis.get('nota_final_b', 0)}%;">
                            <span class="analysis-score-text">{analysis.get('nota_final_b', 0)}%</span>
                        </div>
                        <div class="analysis-score-label">Compatibilidade B</div>
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