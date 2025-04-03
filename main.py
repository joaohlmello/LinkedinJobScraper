from flask import Flask, render_template, request, flash, send_file, session, redirect, jsonify
import os
import logging
import threading
from datetime import datetime
from linkedin_scraper import get_results_html, export_to_csv, export_to_excel

# Variável global para armazenar o progresso do processamento
processing_progress = {
    'total': 0,
    'current': 0,
    'status': 'idle',
    'message': '',
    'results': None
}

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Check if Gemini API key is available
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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
                
                results_html = get_results_html(linkedin_urls, analyze_jobs=analyze_jobs)
                
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
    if 'linkedin_urls' not in session or not session['linkedin_urls']:
        flash('No data to export. Please submit some LinkedIn job URLs first.', 'warning')
        return redirect('/')
    
    # Get URLs from session
    linkedin_urls = session['linkedin_urls']
    
    try:
        # Generate CSV file
        csv_buffer = export_to_csv(linkedin_urls)
        if not csv_buffer:
            flash('Failed to generate CSV file.', 'danger')
            return redirect('/')
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'linkedin_jobs_{timestamp}.csv'
        
        # Send the file to the user
        return send_file(
            csv_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
    except Exception as e:
        logger.error(f"Error exporting to CSV: {str(e)}")
        flash(f'Failed to export to CSV: {str(e)}', 'danger')
        return redirect('/')

@app.route('/export/excel', methods=['GET'])
def export_excel():
    """
    Export LinkedIn job data to Excel.
    """
    if 'linkedin_urls' not in session or not session['linkedin_urls']:
        flash('No data to export. Please submit some LinkedIn job URLs first.', 'warning')
        return redirect('/')
    
    # Get URLs from session
    linkedin_urls = session['linkedin_urls']
    
    try:
        # Generate Excel file
        excel_buffer = export_to_excel(linkedin_urls)
        if not excel_buffer:
            flash('Failed to generate Excel file.', 'danger')
            return redirect('/')
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'linkedin_jobs_{timestamp}.xlsx'
        
        # Send the file to the user
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error exporting to Excel: {str(e)}")
        flash(f'Failed to export to Excel: {str(e)}', 'danger')
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
    
    # Armazenar URLs na sessão para exportação
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
            results_html = get_results_html(
                urls, 
                analyze_jobs=analyze_jobs,
                progress_callback=update_progress
            )
            logger.debug(f"Chamada para get_results_html concluída. Resultado vazio? {results_html is None}")
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
