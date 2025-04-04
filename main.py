from flask import Flask, render_template, request, flash, send_file, session, redirect, jsonify
import os
import logging
import threading
from datetime import datetime
from linkedin_scraper import get_results_html, export_to_csv, export_to_excel, process_linkedin_urls

# Variável global para armazenar o progresso do processamento
processing_progress = {
    'total': 0,             # Total de URLs no lote atual
    'current': 0,           # Progresso atual no lote
    'status': 'idle',       # Status do processamento (idle, processing, completed, etc)
    'message': '',          # Mensagem atual
    'results': None,        # Resultados HTML do lote atual
    'analyze_jobs': False,  # Flag para análise com Gemini
    'df_json': None,        # DataFrame JSON do lote atual
    'urls': [],             # URLs do lote atual
    'batch_size': 10,       # Tamanho de cada lote (padrão: 10)
    'total_batches': 0,     # Número total de lotes
    'current_batch': 0,     # Lote atual sendo processado
    'all_batches': [],      # Lista com todos os lotes
    'processed_batches': [] # Lista de lotes já processados e seus resultados
}

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Check if Gemini API key is available
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
logger.debug(f"Gemini API Key está disponível: {GEMINI_API_KEY is not None}")

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Home route for the LinkedIn Job Scraper app.
    Handles both GET and POST requests.
    """
    results_html = None
    
    if request.method == 'POST':
        # Get LinkedIn URLs from the form
        linkedin_urls_text = request.form.get('linkedin_urls', '')
        linkedin_urls_raw = [url.strip() for url in linkedin_urls_text.split('\n') if url.strip()]
        
        # Remover URLs duplicados mantendo a ordem original
        linkedin_urls = []
        seen_urls = set()
        for url in linkedin_urls_raw:
            if url not in seen_urls:
                linkedin_urls.append(url)
                seen_urls.add(url)
        
        # Verificar se há duplicatas e notificar o usuário
        if len(linkedin_urls) < len(linkedin_urls_raw):
            duplicates_removed = len(linkedin_urls_raw) - len(linkedin_urls)
            flash(f'{duplicates_removed} URL(s) duplicado(s) foram removidos para otimizar o processamento.', 'info')
            
        # Check if user wants to analyze jobs with Gemini AI
        analyze_jobs = 'analyze_jobs' in request.form
        
        if not linkedin_urls:
            flash('Please enter at least one LinkedIn job URL.', 'danger')
        else:
            # Store the URLs in the session for export functionality
            session['linkedin_urls'] = linkedin_urls
            
            # Process the URLs and get results
            try:
                # Analisar jobs se solicitado e se a API do Gemini estiver disponível
                if analyze_jobs and not GEMINI_API_KEY:
                    flash('Análise com Gemini AI solicitada, mas a chave de API não está disponível.', 'warning')
                    analyze_jobs = False
                
                # Agora get_results_html retorna tanto o HTML quanto o DataFrame para exportação
                results_html, df_export = get_results_html(linkedin_urls, analyze_jobs=analyze_jobs)
                
                # Armazenar o DataFrame para exportação na sessão
                if df_export is not None:
                    try:
                        df_json = df_export.to_json(orient='records')
                        session['processed_data'] = df_json
                        logger.debug(f"DataFrame armazenado na sessão para exportação. Tamanho: {len(df_json)}")
                        session['analyze_jobs'] = analyze_jobs
                    except Exception as e:
                        logger.error(f"Erro ao armazenar DataFrame para exportação: {str(e)}")
                
                if "Error" in results_html:
                    flash('There was an error processing one or more URLs. Check the results below.', 'warning')
                else:
                    success_msg = 'LinkedIn job information extracted successfully!'
                    if analyze_jobs:
                        success_msg += ' Análise de compatibilidade com Gemini AI incluída.'
                    flash(success_msg, 'success')
            except Exception as e:
                logger.error(f"Error processing URLs: {str(e)}")
                flash(f'An error occurred: {str(e)}', 'danger')
    
    # Check if we have previous results to display
    has_results = 'linkedin_urls' in session and session['linkedin_urls']
    
    # Verificar se o Gemini API está disponível para o template
    gemini_available = bool(GEMINI_API_KEY)
    
    return render_template('index.html', 
                          results_html=results_html, 
                          has_results=has_results,
                          gemini_available=gemini_available)

@app.route('/export/csv', methods=['GET'])
def export_csv():
    """
    Exporta os dados de vagas do LinkedIn para CSV.
    Se o parâmetro batch_index for fornecido, exporta apenas os dados do lote específico.
    Caso contrário, exporta todos os dados disponíveis.
    """
    global processing_progress
    batch_index = request.args.get('batch_index')
    
    try:
        if batch_index is not None:
            # Exportar um lote específico
            batch_index = int(batch_index)
            return export_batch_csv(batch_index)
        else:
            # Exportar todos os dados disponíveis (comportamento padrão anterior)
            return export_all_csv()
    except ValueError:
        flash('Índice de lote inválido.', 'danger')
        return redirect('/')
    except Exception as e:
        logger.error(f"Erro ao exportar para CSV: {str(e)}")
        flash(f'Falha ao exportar para CSV: {str(e)}', 'danger')
        return redirect('/')

def export_all_csv():
    """
    Exporta todos os dados de vagas do LinkedIn para CSV.
    """
    global processing_progress
    logger.debug(f"Session keys: {session.keys()}")
    
    # Primeiro verificar no processamento global
    urls = processing_progress.get('urls', [])
    analyze_jobs = processing_progress.get('analyze_jobs', False)
    df_json = processing_progress.get('df_json')
    
    # Se não tivermos URLs no objeto global, tentar buscar da sessão (compatibilidade)
    if not urls and 'linkedin_urls' in session:
        urls = session['linkedin_urls']
    
    # Verificar se temos URLs para processar
    if not urls:
        flash('Não há dados para exportar. Por favor, envie alguns URLs do LinkedIn primeiro.', 'warning')
        return redirect('/')
    
    logger.debug(f"Exportando com análise Gemini: {analyze_jobs}")
    
    # Verificar se já temos dados processados
    if df_json:
        logger.debug("Usando dados processados do objeto global para exportação CSV")
    else:
        # Tentar pegar da sessão como fallback (compatibilidade)
        df_json = session.get('processed_data')
        if df_json:
            logger.debug("Usando dados processados da sessão para exportação CSV")
        else:
            logger.debug("Não há dados processados, será necessário reprocessar")
    
    try:
        # Gerar arquivo CSV
        csv_buffer = export_to_csv(urls, df_json, analyze_jobs)
        if not csv_buffer:
            flash('Falha ao gerar arquivo CSV.', 'danger')
            return redirect('/')
        
        # Gerar nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'linkedin_jobs_{timestamp}.csv'
        
        # Enviar o arquivo para o usuário
        return send_file(
            csv_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
    except Exception as e:
        logger.error(f"Erro ao exportar para CSV: {str(e)}")
        flash(f'Falha ao exportar para CSV: {str(e)}', 'danger')
        return redirect('/')

def export_batch_csv(batch_index):
    """
    Exporta os dados de um lote específico para CSV.
    
    Args:
        batch_index (int): Índice do lote a ser exportado
    
    Returns:
        Response: Arquivo CSV para download
    """
    global processing_progress
    
    # Verificar se o batch_index é válido
    if batch_index < 0 or batch_index >= len(processing_progress['processed_batches']):
        flash(f'Lote {batch_index} não encontrado.', 'danger')
        return redirect('/')
    
    # Obter os dados do lote específico
    batch_data = processing_progress['processed_batches'][batch_index]
    urls = batch_data.get('urls', [])
    df_json = batch_data.get('df_json')
    analyze_jobs = processing_progress.get('analyze_jobs', False)
    
    # Verificar se temos os dados necessários
    if not urls or not df_json:
        flash(f'Dados do lote {batch_index} indisponíveis ou incompletos.', 'warning')
        return redirect('/')
    
    logger.debug(f"Exportando lote {batch_index} com {len(urls)} URLs para CSV")
    
    try:
        # Gerar arquivo CSV apenas para este lote
        csv_buffer = export_to_csv(urls, df_json, analyze_jobs)
        if not csv_buffer:
            flash(f'Falha ao gerar arquivo CSV para o lote {batch_index}.', 'danger')
            return redirect('/')
        
        # Gerar nome do arquivo com timestamp e índice do lote
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'linkedin_jobs_batch_{batch_index}_{timestamp}.csv'
        
        # Enviar o arquivo para o usuário
        return send_file(
            csv_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
    except Exception as e:
        logger.error(f"Erro ao exportar lote {batch_index} para CSV: {str(e)}")
        flash(f'Falha ao exportar lote {batch_index} para CSV: {str(e)}', 'danger')
        return redirect('/')

# Rota de exportação para Excel removida conforme solicitado pelo usuário
# A exportação em CSV é suficiente para as necessidades atuais

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('index.html', error="Server error occurred"), 500

@app.route('/process_async', methods=['POST'])
def process_async():
    """
    Processa URLs do LinkedIn de forma assíncrona e atualiza o progresso
    Divide os URLs em lotes para processamento mais rápido e seguro
    """
    global processing_progress
    
    # Log da solicitação para depuração
    logger.debug(f"Solicitação de processamento assíncrono recebida: {request.form}")
    
    # Verificar se já está em processamento
    if processing_progress['status'] == 'processing':
        logger.debug("Processamento já em andamento")
        return jsonify({
            'success': False,
            'message': 'Já existe um processamento em andamento'
        })
    
    # Obter URLs do formulário
    linkedin_urls_text = request.form.get('linkedin_urls', '')
    linkedin_urls_raw = [url.strip() for url in linkedin_urls_text.split('\n') if url.strip()]
    
    # Remover URLs duplicados mantendo a ordem original
    linkedin_urls = []
    seen_urls = set()
    for url in linkedin_urls_raw:
        if url not in seen_urls:
            linkedin_urls.append(url)
            seen_urls.add(url)
    
    # Verificar se há duplicatas e notificar 
    message = 'Por favor, insira pelo menos uma URL de vaga do LinkedIn'
    if len(linkedin_urls) < len(linkedin_urls_raw):
        duplicates_removed = len(linkedin_urls_raw) - len(linkedin_urls)
        message = f'Removidos {duplicates_removed} URLs duplicados para otimizar o processamento'
        logger.debug(message)
    
    # Verificar se há URLs para processar
    if not linkedin_urls:
        logger.debug("Nenhuma URL fornecida")
        return jsonify({
            'success': False,
            'message': message
        })
    
    # Verificar se o usuário deseja analisar vagas com Gemini AI
    analyze_jobs = 'analyze_jobs' in request.form
    logger.debug(f"Analisar vagas com Gemini AI: {analyze_jobs}")
    
    # Verificar se a API do Gemini está disponível
    if analyze_jobs and not GEMINI_API_KEY:
        logger.warning("Análise com Gemini solicitada, mas API key não disponível")
        analyze_jobs = False
    
    # Obter tamanho do lote do formulário ou usar padrão
    try:
        batch_size = int(request.form.get('batch_size', 10))
        if batch_size < 1 or batch_size > 50:
            batch_size = 10  # Valor padrão seguro
    except ValueError:
        batch_size = 10
    
    # Dividir URLs em lotes do tamanho especificado
    batches = []
    total_urls = len(linkedin_urls)
    
    # Criar lotes de URLs
    for i in range(0, total_urls, batch_size):
        batch = linkedin_urls[i:i+batch_size]
        batches.append(batch)
    
    # Inicializar o progresso global
    processing_progress['status'] = 'processing'
    processing_progress['total'] = len(batches[0]) if batches else 0  # Total do primeiro lote
    processing_progress['current'] = 0
    processing_progress['message'] = 'Preparando lotes para processamento...'
    processing_progress['results'] = None
    processing_progress['analyze_jobs'] = analyze_jobs
    processing_progress['df_json'] = None
    processing_progress['all_batches'] = batches
    processing_progress['total_batches'] = len(batches)
    processing_progress['current_batch'] = 0
    processing_progress['batch_size'] = batch_size
    processing_progress['processed_batches'] = []
    
    # Log de informações sobre os lotes
    logger.debug(f"Total de URLs: {total_urls}")
    logger.debug(f"Tamanho do lote: {batch_size}")
    logger.debug(f"Número total de lotes: {len(batches)}")
    
    # Armazenar URLs completos na sessão para compatibilidade
    session['linkedin_urls'] = linkedin_urls
    
    # Iniciar processamento em segundo plano
    thread = threading.Thread(
        target=process_batches_background, 
        args=(batches, analyze_jobs)
    )
    thread.daemon = True
    thread.start()
    
    logger.debug("Thread de processamento em lotes iniciada")
    
    return jsonify({
        'success': True,
        'message': f'Processamento iniciado com {len(batches)} lotes de {batch_size} URLs'
    })

def process_urls_background(urls, analyze_jobs=False):
    """
    Função para processar URLs em segundo plano e atualizar o progresso
    """
    global processing_progress
    
    try:
        logger.debug(f"Iniciando processamento de {len(urls)} URLs em segundo plano. Análise de vagas: {analyze_jobs}")
        logger.debug(f"URLs a serem processadas: {urls}")
        
        # Garantir que temos um valor inicial para os resultados
        processing_progress['results'] = None
        
        # Processar URLs e obter resultados
        results_html = None
        try:
            # Extrair dados e armazenar o DataFrame para exportação
            from linkedin_scraper import process_linkedin_urls, get_results_html
            import pandas as pd
            
            # Processar e obter resultados HTML formatados e DataFrame para exportação
            results_html, df_export = get_results_html(
                urls, 
                analyze_jobs=analyze_jobs,
                progress_callback=update_progress
            )
            logger.debug(f"Chamada para get_results_html concluída. Resultado vazio? {results_html is None}")
            
            # A sessão só pode ser modificada dentro de um contexto de requisição
            # Vamos armazenar apenas no objeto de progresso global
            processing_progress['analyze_jobs'] = analyze_jobs
            
            # Armazenar o DataFrame pré-processado na sessão para exportação
            try:
                logger.debug("Preparando DataFrame para armazenamento na sessão")
                
                # O DataFrame de exportação já contém todos os dados e é retornado por get_results_html
                # Convertemos diretamente para JSON, sem precisar reprocessar nada
                if df_export is not None:
                    df_json = df_export.to_json(orient='records')
                    
                    # Armazenar no objeto de progresso global em vez de na sessão
                    processing_progress['df_json'] = df_json
                    logger.debug(f"DataFrame convertido para JSON e armazenado no objeto de progresso. Tamanho: {len(df_json)}")
                else:
                    logger.error("DataFrame de exportação não retornado pela função get_results_html")
            except Exception as df_e:
                logger.error(f"Erro ao processar DataFrame para sessão: {str(df_e)}")
                # Não impede o fluxo principal se falhar
        
        except Exception as inner_e:
            logger.error(f"Exceção capturada ao chamar get_results_html: {str(inner_e)}")
            import traceback
            logger.error(traceback.format_exc())
            # Criar uma mensagem de erro formatada como HTML para exibir na interface
            results_html = f"""
            <div class="alert alert-danger">
                <h4 class="alert-heading">Erro ao processar URLs</h4>
                <p>Ocorreu um erro durante a extração de dados do LinkedIn.</p>
                <hr>
                <p class="mb-0">Detalhes do erro: {str(inner_e)}</p>
            </div>
            """
        
        # Verificar se os resultados foram obtidos
        if results_html:
            logger.debug(f"Resultados HTML obtidos. Tamanho: {len(results_html)}")
            # Atualizar progresso com resultados
            processing_progress['results'] = results_html
            processing_progress['status'] = 'completed'
            processing_progress['message'] = 'Processamento concluído com sucesso!'
            
            # Log adicional para confirmação
            logger.debug("Status atualizado para 'completed' e resultados armazenados")
        else:
            # Se não houver resultados, criar uma mensagem padrão
            logger.error("Não foi possível obter resultados HTML (resultado vazio)")
            error_html = """
            <div class="alert alert-warning">
                <h4 class="alert-heading">Sem resultados</h4>
                <p>Não foram encontrados resultados para as URLs fornecidas. Verifique se as URLs são válidas vagas do LinkedIn.</p>
            </div>
            """
            processing_progress['results'] = error_html
            processing_progress['status'] = 'completed'  # Marcamos como completo mesmo assim
            processing_progress['message'] = 'Processamento concluído sem resultados'
            
    except Exception as e:
        logger.error(f"Erro no processamento assíncrono: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Criar uma mensagem de erro formatada
        error_html = f"""
        <div class="alert alert-danger">
            <h4 class="alert-heading">Erro no processamento</h4>
            <p>Ocorreu um erro durante o processamento das URLs.</p>
            <hr>
            <p class="mb-0">Detalhes do erro: {str(e)}</p>
        </div>
        """
        
        # Atualizar o progresso com a mensagem de erro
        processing_progress['results'] = error_html
        processing_progress['status'] = 'completed'  # Marcamos como completo para exibir o erro
        processing_progress['message'] = f'Ocorreu um erro: {str(e)}'

def update_progress(current, total, message):
    """
    Callback para atualizar o progresso do processamento
    """
    global processing_progress
    processing_progress['current'] = current
    processing_progress['total'] = total
    processing_progress['message'] = message

def process_batches_background(batches, analyze_jobs=False):
    """
    Processa lotes de URLs sequencialmente
    
    Args:
        batches (list): Lista de lotes, cada lote é uma lista de URLs
        analyze_jobs (bool): Se True, analisa as vagas com a API Gemini
    """
    global processing_progress
    
    try:
        total_batches = len(batches)
        logger.debug(f"Iniciando processamento em lotes: {total_batches} lotes")
        
        # Lista para armazenar resultados de todos os lotes
        all_results_html = []
        all_df_jsons = []
        
        # Processar cada lote sequencialmente
        for batch_index, batch in enumerate(batches):
            # Atualizar informações do lote atual
            processing_progress['current_batch'] = batch_index + 1
            processing_progress['urls'] = batch
            processing_progress['total'] = len(batch)
            processing_progress['current'] = 0
            processing_progress['message'] = f'Processando lote {batch_index+1} de {total_batches}...'
            processing_progress['results'] = None
            processing_progress['df_json'] = None
            
            logger.debug(f"Iniciando processamento do lote {batch_index+1}/{total_batches} com {len(batch)} URLs")
            
            # Processar URLs do lote atual
            try:
                from linkedin_scraper import get_results_html
                import pandas as pd
                
                # Função de callback para atualizar progresso do lote atual
                def batch_progress_callback(current, total, message):
                    update_progress(current, total, f"Lote {batch_index+1}/{total_batches}: {message}")
                
                # Processar o lote atual
                results_html, df_export = get_results_html(
                    batch,
                    analyze_jobs=analyze_jobs,
                    progress_callback=batch_progress_callback
                )
                
                # Armazenar resultados temporários
                if results_html and df_export is not None:
                    # Converter DataFrame para JSON
                    df_json = df_export.to_json(orient='records')
                    
                    # Armazenar resultados do lote atual
                    processing_progress['results'] = results_html
                    processing_progress['df_json'] = df_json
                    
                    # Adicionar resultados à lista de todos os lotes processados
                    batch_result = {
                        'batch_index': batch_index,
                        'urls': batch,
                        'results_html': results_html,
                        'df_json': df_json
                    }
                    processing_progress['processed_batches'].append(batch_result)
                    
                    # Adicionar aos resultados acumulados
                    all_results_html.append(results_html)
                    all_df_jsons.append(df_json)
                    
                    logger.debug(f"Lote {batch_index+1}/{total_batches} processado com sucesso")
                else:
                    error_html = f"""
                    <div class="alert alert-warning">
                        <h4 class="alert-heading">Sem resultados no lote {batch_index+1}</h4>
                        <p>Não foram encontrados resultados para as URLs deste lote.</p>
                    </div>
                    """
                    processing_progress['results'] = error_html
                    
                    # Adicionar erro à lista de lotes processados
                    batch_result = {
                        'batch_index': batch_index,
                        'urls': batch,
                        'results_html': error_html,
                        'df_json': None,
                        'error': True
                    }
                    processing_progress['processed_batches'].append(batch_result)
                    
                    # Adicionar aos resultados acumulados
                    all_results_html.append(error_html)
                    
                    logger.warning(f"Lote {batch_index+1}/{total_batches} não retornou resultados")
                
            except Exception as batch_error:
                logger.error(f"Erro ao processar lote {batch_index+1}/{total_batches}: {str(batch_error)}")
                
                # Criar mensagem de erro formatada
                error_html = f"""
                <div class="alert alert-danger">
                    <h4 class="alert-heading">Erro no lote {batch_index+1}</h4>
                    <p>Ocorreu um erro durante o processamento deste lote.</p>
                    <hr>
                    <p class="mb-0">Detalhes do erro: {str(batch_error)}</p>
                </div>
                """
                
                # Armazenar erro nos resultados do lote
                processing_progress['results'] = error_html
                
                # Adicionar erro à lista de lotes processados
                batch_result = {
                    'batch_index': batch_index,
                    'urls': batch,
                    'results_html': error_html,
                    'df_json': None,
                    'error': True
                }
                processing_progress['processed_batches'].append(batch_result)
                
                # Adicionar aos resultados acumulados
                all_results_html.append(error_html)
        
        # Finalizar o processamento
        if all_results_html:
            # Combinar resultados de todos os lotes em um único HTML
            combined_html = "".join(all_results_html)
            processing_progress['results'] = combined_html
            
            # Indicar que todos os lotes foram processados
            processing_progress['status'] = 'completed'
            processing_progress['message'] = f'Todos os {total_batches} lotes processados com sucesso!'
            logger.info(f"Processamento de todos os {total_batches} lotes concluído")
        else:
            # Se não houver resultados, marcar como erro
            error_html = """
            <div class="alert alert-danger">
                <h4 class="alert-heading">Sem resultados</h4>
                <p>Nenhum dos lotes retornou resultados. Verifique se as URLs são válidas.</p>
            </div>
            """
            processing_progress['results'] = error_html
            processing_progress['status'] = 'completed'
            processing_progress['message'] = 'Processamento concluído sem resultados'
            logger.error("Nenhum dos lotes retornou resultados")
    
    except Exception as e:
        logger.error(f"Erro no processamento em lotes: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Criar mensagem de erro formatada
        error_html = f"""
        <div class="alert alert-danger">
            <h4 class="alert-heading">Erro no processamento em lotes</h4>
            <p>Ocorreu um erro durante o processamento dos lotes.</p>
            <hr>
            <p class="mb-0">Detalhes do erro: {str(e)}</p>
        </div>
        """
        
        # Atualizar o progresso com a mensagem de erro
        processing_progress['results'] = error_html
        processing_progress['status'] = 'completed'
        processing_progress['message'] = f'Ocorreu um erro: {str(e)}'

@app.route('/check_progress', methods=['GET'])
def check_progress():
    """
    Retorna o status atual do processamento
    """
    global processing_progress
    
    logger.debug(f"Verificação de progresso. Status atual: {processing_progress['status']}")
    
    # Para depuração, vamos verificar se os resultados existem quando estiver completo
    if processing_progress['status'] == 'completed':
        has_results = processing_progress['results'] is not None
        results_length = len(processing_progress['results']) if has_results else 0
        logger.debug(f"Processamento completo. Resultados disponíveis: {has_results}, Tamanho: {results_length}")
    
    # Calcular a porcentagem de conclusão (evitando divisão por zero)
    percent = 0
    if processing_progress['total'] > 0:
        percent = int((processing_progress['current'] / processing_progress['total']) * 100)
    
    # Calcular progresso total considerando todos os lotes
    batch_percent = 0
    if processing_progress['total_batches'] > 0:
        # Progresso do lote atual + progresso dos lotes anteriores
        completed_batches = processing_progress['current_batch'] - 1
        if completed_batches > 0:
            batch_percent = (completed_batches * 100) / processing_progress['total_batches']
        
        # Adicionar a porcentagem do lote atual proporcional ao total
        if processing_progress['total_batches'] > 0:
            current_batch_weight = 1 / processing_progress['total_batches']
            batch_percent += (percent / 100) * current_batch_weight * 100
    
    # Preparar a resposta com informações de lotes
    response = {
        'status': processing_progress['status'],
        'current': processing_progress['current'],
        'total': processing_progress['total'],
        'percent': percent,  # Progresso do lote atual
        'batch_percent': int(batch_percent),  # Progresso total considerando todos os lotes
        'current_batch': processing_progress['current_batch'],
        'total_batches': processing_progress['total_batches'],
        'message': processing_progress['message'],
        'results': processing_progress['results'] if processing_progress['status'] == 'completed' else None,
        'processed_batches': len(processing_progress['processed_batches']),
        'batches_info': [
            {
                'batch_index': b.get('batch_index'),
                'urls_count': len(b.get('urls', [])),
                'has_error': b.get('error', False)
            } 
            for b in processing_progress['processed_batches']
        ]
    }
    
    logger.debug(f"Resposta de verificação de progresso: {response['status']}, " +
                f"Lote atual: {response['percent']}% (Lote {response['current_batch']}/{response['total_batches']}), " +
                f"Total: {response['batch_percent']}%, {response['message']}")
    
    return jsonify(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
