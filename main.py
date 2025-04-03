from flask import Flask, render_template, request, flash, send_file, session, redirect, jsonify
import os
import logging
import threading
from datetime import datetime
from linkedin_scraper import get_results_html, export_to_csv, export_to_excel, process_linkedin_urls

# Variável global para armazenar o progresso do processamento
processing_progress = {
    'total': 0,
    'current': 0,
    'status': 'idle',
    'message': '',
    'results': None,
    'analyze_jobs': False,
    'df_json': None,
    'urls': []
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
        linkedin_urls = [url.strip() for url in linkedin_urls_text.split('\n') if url.strip()]
        
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
    Export LinkedIn job data to CSV.
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

@app.route('/export/excel', methods=['GET'])
def export_excel():
    """
    Export LinkedIn job data to Excel.
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
    
    logger.debug(f"Exportando {len(urls)} URLs para Excel")
    logger.debug(f"Exportando com análise Gemini: {analyze_jobs}")
    
    # Verificar se já temos dados processados
    if df_json:
        logger.debug("Usando dados processados do objeto global para exportação Excel")
    else:
        # Tentar pegar da sessão como fallback (compatibilidade)
        df_json = session.get('processed_data')
        if df_json:
            logger.debug("Usando dados processados da sessão para exportação Excel")
        else:
            logger.debug("Não há dados processados, será necessário reprocessar")
    
    try:
        # Gerar arquivo Excel
        excel_buffer = export_to_excel(urls, df_json, analyze_jobs)
        if not excel_buffer:
            flash('Falha ao gerar arquivo Excel.', 'danger')
            return redirect('/')
        
        # Gerar nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'linkedin_jobs_{timestamp}.xlsx'
        
        # Definir o MIME type correto para Excel
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        # Usar configuração que funciona em múltiplas versões de Flask
        logger.debug(f"Enviando arquivo Excel: {filename}")
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
    except Exception as e:
        logger.error(f"Erro ao exportar para Excel: {str(e)}")
        flash(f'Falha ao exportar para Excel: {str(e)}', 'danger')
        return redirect('/')

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
    linkedin_urls = [url.strip() for url in linkedin_urls_text.split('\n') if url.strip()]
    
    # Verificar se há URLs para processar
    if not linkedin_urls:
        logger.debug("Nenhuma URL fornecida")
        return jsonify({
            'success': False,
            'message': 'Por favor, insira pelo menos uma URL de vaga do LinkedIn'
        })
    
    logger.debug(f"URLs para processar: {linkedin_urls}")
    
    # Verificar se o usuário deseja analisar vagas com Gemini AI
    analyze_jobs = 'analyze_jobs' in request.form
    logger.debug(f"Analisar vagas com Gemini AI: {analyze_jobs}")
    
    # Verificar se a API do Gemini está disponível
    if analyze_jobs and not GEMINI_API_KEY:
        logger.warning("Análise com Gemini solicitada, mas API key não disponível")
        analyze_jobs = False
    
    # Inicializar o progresso
    processing_progress['status'] = 'processing'
    processing_progress['total'] = len(linkedin_urls)
    processing_progress['current'] = 0
    processing_progress['message'] = 'Iniciando processamento...'
    processing_progress['results'] = None
    processing_progress['urls'] = linkedin_urls.copy()  # Armazenar URLs no objeto global
    processing_progress['analyze_jobs'] = analyze_jobs  # Armazenar flag de análise
    processing_progress['df_json'] = None  # Limpar dados anteriores
    
    # Armazenar URLs na sessão para exportação (para compatibilidade)
    session['linkedin_urls'] = linkedin_urls
    
    # Iniciar processamento em segundo plano
    thread = threading.Thread(
        target=process_urls_background, 
        args=(linkedin_urls, analyze_jobs)
    )
    thread.daemon = True
    thread.start()
    
    logger.debug("Thread de processamento iniciada")
    
    return jsonify({
        'success': True,
        'message': 'Processamento iniciado'
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
    
    # Preparar a resposta
    response = {
        'status': processing_progress['status'],
        'current': processing_progress['current'],
        'total': processing_progress['total'],
        'percent': percent,
        'message': processing_progress['message'],
        'results': processing_progress['results'] if processing_progress['status'] == 'completed' else None
    }
    
    logger.debug(f"Resposta de verificação de progresso: {response['status']}, {response['percent']}%, {response['message']}")
    
    return jsonify(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
