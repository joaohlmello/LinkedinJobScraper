import os
import json
import logging
import time
import re
import base64
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content

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
            genai.configure(api_key=api_key)
            self.model_name = "gemini-2.5-flash-preview-04-17"
            
            # Configuração de geração
            self.generation_config = {
                "temperature": 0,
                "top_p": 0.5,
                "top_k": 64,
                "max_output_tokens": 65536,
                "response_schema": content.Schema(
                    type = content.Type.OBJECT,
                    required = ["nota_industria_contexto", "nota_cargos_anteriores", "nota_requisitos", "nota_final", "fraquezas", "idioma_descricao", "tipo_vaga", "industria_vaga", "foco_vaga"],
                    properties = {
                        "nota_industria_contexto": content.Schema(
                            type = content.Type.INTEGER,
                        ),
                        "nota_cargos_anteriores": content.Schema(
                            type = content.Type.INTEGER,
                        ),
                        "nota_requisitos": content.Schema(
                            type = content.Type.INTEGER,
                        ),
                        "nota_final": content.Schema(
                            type = content.Type.INTEGER,
                        ),
                        "fraquezas": content.Schema(
                            type = content.Type.STRING,
                        ),
                        "idioma_descricao": content.Schema(
                            type = content.Type.STRING,
                            enum = ["ingles", "portugues"],
                        ),
                        "tipo_vaga": content.Schema(
                            type = content.Type.STRING,
                            enum = ["projeto", "programa", "portfolio", "pmo", "planejamento", "produto", "dados_tecnico", "dados_bi", "inteligencia_mercado", "operacoes", "processo", "gestao_mudanca", "outro"],
                        ),
                        "industria_vaga": content.Schema(
                            type = content.Type.STRING,
                        ),
                        "foco_vaga": content.Schema(
                            type = content.Type.STRING,
                        ),
                    },
                ),
                "response_mime_type": "application/json",
            }
            
            # Configurar o prompt base
            self.system_prompt = self._get_system_prompt()
            
            # Criar o modelo
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.generation_config,
                system_instruction=self.system_prompt
            )
            
            logger.info(f"Analisador de vagas inicializado com o modelo {self.model_name}")
        except Exception as e:
            logger.error(f"Erro ao inicializar o cliente Gemini: {str(e)}")
            raise ValueError(f"Não foi possível inicializar o cliente Gemini: {str(e)}")
    
    def _get_system_prompt(self):
        """
        Retorna o prompt do sistema que orienta o modelo sobre como analisar as vagas.
        """
        return """#CONTEXTO  
Avalie o "CURRICULO", como um Diretor de RH faria para avaliar um candidato externo para uma vaga estratégica, sem otimismo em relação ao candidato

#METODOLOGIA DE AVALIAÇÃO
-Requisitos: Disseque cada requisito explícito. Atribua uma nota binária de aderência (0 ou 1) justificada para cada um
-Cargos Anteriores: Avalie a trajetória profissional e compatibilidade de cargos e responsabilidades anteriores. Dê peso maior ao cargo mais recente. Seja crítico e direto.
-Indústria e Contexto da Vaga: Avalie a indústria/setor da vaga e o contexto específico de negócio/área. Identifique: posição hierárquica, localização na estrutura, relações de reporte, produtos gerenciados, entregas esperadas, fase do ciclo de vida. 
-Cálculo de Aderência Ponderada: (20% indústria / contexto) + (40% cargos anteriores) + (40% requisitos).
-Fraquezas: Liste fraquezas reais e concretas que representam um problema específico para esta vaga. Inclua pontos que poderiam barrar a contratação ou gerar questionamentos durante um processo seletivo.

#ESTRUTURA DO RETORNO
1. idioma_descricao: "ingles" ou "portugues"
2. tipo_vaga: "projeto", "programa", "portfolio", "pmo", "planejamento", "produto", "dados_tecnico", "dados_bi", "inteligencia_mercado", "operacoes", "processo", "gestao_mudanca", "outro"
3. industria_vaga: string com descrição
4. foco_vaga: string com descrição
5. fraquezas: string com descrição
6. nota_industria_contexto: inteiro de 0 a 100
7. nota_cargos_anteriores: inteiro de 0 a 100
8. nota_requisitos: inteiro de 0 a 100
9. nota_final: inteiro de 0 a 100"""

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
            
            # Fazer a chamada à API do Gemini
            logger.info(f"Enviando solicitação de análise para vaga: {job_title}")
            
            try:
                # Iniciando uma sessão de chat
                chat_session = self.model.start_chat(history=[])
                
                # Enviar a mensagem e obter a resposta
                response = chat_session.send_message(input_text)
                
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
                    
                    logger.info(f"Análise concluída para vaga: {job_title} - Compatibilidade: {analysis_data.get('nota_final', 'N/A')}%")
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
                <div class="col-md-6">
                    <div class="analysis-details-card">
                        <h5>Idioma</h5>
                        <p>{analysis.get('idioma_descricao', 'Não informado')}</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="analysis-details-card">
                        <h5>Tipo de Vaga</h5>
                        <p>{analysis.get('tipo_vaga', 'Não informado')}</p>
                    </div>
                </div>
            </div>
            
            <div class="row mb-3">
                <div class="col-md-6">
                    <div class="analysis-details-card">
                        <h5>Indústria/Contexto</h5>
                        <p>{analysis.get('industria_vaga', 'Não informado')}</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="analysis-details-card">
                        <h5>Foco da Vaga</h5>
                        <p>{analysis.get('foco_vaga', 'Não informado')}</p>
                    </div>
                </div>
            </div>
            
            <div class="row mb-4">
                <div class="col-md-3">
                    <div class="analysis-details-card">
                        <h5>Indústria/Contexto</h5>
                        <div class="progress">
                            <div class="progress-bar bg-info" role="progressbar" style="width: {analysis.get('nota_industria_contexto', 0)}%;" 
                                aria-valuenow="{analysis.get('nota_industria_contexto', 0)}" aria-valuemin="0" aria-valuemax="100">
                                {analysis.get('nota_industria_contexto', 0)}%
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="analysis-details-card">
                        <h5>Cargos Anteriores</h5>
                        <div class="progress">
                            <div class="progress-bar bg-info" role="progressbar" style="width: {analysis.get('nota_cargos_anteriores', 0)}%;" 
                                aria-valuenow="{analysis.get('nota_cargos_anteriores', 0)}" aria-valuemin="0" aria-valuemax="100">
                                {analysis.get('nota_cargos_anteriores', 0)}%
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
                    <div class="analysis-score-container">
                        <div class="analysis-score-circle" style="--score: {analysis.get('nota_final', 0)}%;">
                            <span class="analysis-score-text">{analysis.get('nota_final', 0)}%</span>
                        </div>
                        <div class="analysis-score-label">Compatibilidade</div>
                    </div>
                </div>
            </div>
            
            <div class="row mb-3">
                <div class="col-md-12">
                    <div class="analysis-details-card">
                        <h5>Fraquezas</h5>
                        <p>{format_text_with_breaks(analysis.get('fraquezas', 'Não informado'))}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    
    return html


# Função para exportar a análise para HTML em uma tabela
def format_jobs_table_html(job_analyses):
    """
    Formata uma lista de análises de vagas como uma tabela HTML.
    
    Args:
        job_analyses (list): Lista de análises de vagas
        
    Returns:
        str: HTML da tabela com os resultados
    """
    if not job_analyses:
        return """
        <div class="alert alert-warning">
            <h4>Nenhuma vaga analisada</h4>
            <p>Nenhuma análise de vaga foi realizada ainda.</p>
        </div>
        """
    
    # Construir a tabela HTML
    html = """
    <div class="table-responsive">
        <table class="table table-striped table-hover">
            <thead class="thead-dark">
                <tr>
                    <th>Empresa</th>
                    <th>Cargo</th>
                    <th>Idioma</th>
                    <th>Tipo de Vaga</th>
                    <th>Indústria/Contexto</th>
                    <th>Foco da Vaga</th>
                    <th>Nota Indústria</th>
                    <th>Nota Cargos</th>
                    <th>Nota Requisitos</th>
                    <th>Compatibilidade</th>
                    <th>Fraquezas</th>
                    <th>Detalhes</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for analysis in job_analyses:
        if "error" in analysis:
            # Mostrar erro em linha da tabela
            html += f"""
            <tr class="table-danger">
                <td>{analysis.get('company_name', 'N/A')}</td>
                <td>{analysis.get('job_title', 'N/A')}</td>
                <td colspan="8">{analysis.get('error', 'Erro na análise')}</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" disabled>Erro</button>
                </td>
            </tr>
            """
        else:
            # Mostrar dados da análise em linha da tabela
            html += f"""
            <tr>
                <td>{analysis.get('company_name', 'N/A')}</td>
                <td>{analysis.get('job_title', 'N/A')}</td>
                <td>{analysis.get('idioma_descricao', 'N/A')}</td>
                <td>{analysis.get('tipo_vaga', 'N/A')}</td>
                <td>{analysis.get('industria_vaga', 'N/A')}</td>
                <td>{analysis.get('foco_vaga', 'N/A')}</td>
                <td>{analysis.get('nota_industria_contexto', 'N/A')}%</td>
                <td>{analysis.get('nota_cargos_anteriores', 'N/A')}%</td>
                <td>{analysis.get('nota_requisitos', 'N/A')}%</td>
                <td class="text-center">
                    <div class="small-score-circle" style="--score: {analysis.get('nota_final', 0)}%;">
                        <span class="small-score-text">{analysis.get('nota_final', 0)}%</span>
                    </div>
                </td>
                <td>{analysis.get('fraquezas', 'N/A')[:100]}...</td>
                <td>
                    <a href="{analysis.get('job_link', '#')}" target="_blank" class="btn btn-sm btn-outline-primary">Ver Vaga</a>
                </td>
            </tr>
            """
    
    html += """
            </tbody>
        </table>
    </div>
    """
    
    return html
