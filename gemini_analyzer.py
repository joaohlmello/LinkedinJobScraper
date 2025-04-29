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
                "top_p": 0.65,
                "top_k": 64,
                "max_output_tokens": 65536,
                "response_schema": content.Schema(
                    type = content.Type.OBJECT,
                    required = ["nota_requisitos", "nota_responsabilidades", "pontos_fracos", "tipo_vaga"],
                    properties = {
                        "nota_requisitos": content.Schema(
                            type = content.Type.INTEGER,
                        ),
                        "nota_responsabilidades": content.Schema(
                            type = content.Type.INTEGER,
                        ),
                        "pontos_fracos": content.Schema(
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
        return """#INSTRUÇÕES
-Execute as tarefas abaixo de forma direta e objetiva.
-Responda sempre em portugues.
-Apresente os resultados estritamente no formato especificado no Passo 4, sem introduções, saudações, explicações adicionais ou qualquer texto não solicitado.

#ENTRADAS
-Descrição da Vaga (JD)
-Currículo (CV)

#Passos 1 e 2: Extrair Requisitos da JD
Identifique e liste os requisitos da JD, agrupando nas categorias abaixo. Considere sinônimos e alternativas ("OU"). Se algum deles não for informado, será "N/A"
-Requisitos Obrigatórios e Desejáveis
-Responsabilidades e Atividades: (Obs: Excluir itens já listados anteriormente)

#Passo 2: Analisar CVs e Pontuar Categorias
Calcule a pontuação (0-100) para cada categoria.

#Passo 4: Apresentar Resultados (Formato Estrito)
Para cada candidato, apresente a informação abaixo, sem nenhuma informação a mais.
-nota_requisitos (0-100)
-nota_responsabilidades (0-100)
-pontos_fracos
-idioma_descricao
-tipo_vaga"""

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

Analisar a compatibilidade entre o currículo do candidato modelo (fornecido no seu contexto) e esta vaga de emprego.
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
                    
                    # Adicionar informações de sistema às análises para exibição
                    analysis_data["system_instructions"] = self.system_prompt
                    
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
    nota_requisitos = analysis.get('nota_requisitos', 'N/A')
    nota_responsabilidades = analysis.get('nota_responsabilidades', 'N/A')
    idioma_descricao = analysis.get('idioma_descricao', 'Não informado')
    tipo_vaga = analysis.get('tipo_vaga', 'Não classificada')
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
            <div class="col-md-4">
                <h5>Compatibilidade</h5>
                <div class="lead mb-2 {compat_class}">
                    <strong>{nota_requisitos}</strong>
                </div>
                <div class="small text-muted">Nota de Requisitos</div>
            </div>
            <div class="col-md-4">
                <h5>Responsabilidades</h5>
                <div class="lead mb-2">
                    <strong>{nota_responsabilidades}</strong>
                </div>
                <div class="small text-muted">Nota de responsabilidades</div>
            </div>
            <div class="col-md-4">
                <h5>Classificação</h5>
                <div><span class="badge bg-info">{tipo_vaga}</span></div>
                <div class="small text-muted">Tipo da vaga</div>
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
        <div class="row mt-3">
            <div class="col-12">
                <div class="small text-muted">
                    <strong>Idioma da vaga:</strong> {idioma_descricao}
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
        nota_requisitos = analysis.get('nota_requisitos', 'N/A')
        nota_responsabilidades = analysis.get('nota_responsabilidades', 'N/A')
        idioma_descricao = analysis.get('idioma_descricao', 'N/A')
        tipo_vaga = analysis.get('tipo_vaga', 'N/A')
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
            <td>{idioma_descricao}</td>
            <td>{tipo_vaga}</td>
        </tr>
        """
        
        rows.append(row)
    
    # Montar a tabela completa
    table = f"""
    <table class="table table-striped">
        <thead>
            <tr>
                <th>Vaga / Empresa</th>
                <th>Nota Requisitos</th>
                <th>Nota Responsabilidades</th>
                <th>Pontos Fracos</th>
                <th>Idioma</th>
                <th>Tipo de Vaga</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>
    """
    
    return table