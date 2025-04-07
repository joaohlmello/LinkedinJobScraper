from flask import Flask, render_template, request, flash, send_file, session, redirect, jsonify
import os
import logging
import threading
import json
from datetime import datetime
from linkedin_scraper import get_results_html, export_to_csv
from models import db, ProcessedBatch, IgnoredURL, UserInputs

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database with this Flask app
db.init_app(app)

# Inicializar o banco de dados
with app.app_context():
    db.create_all()
    logger.debug("Tabelas do banco de dados criadas/verificadas")

# Configuração de autenticação
APP_PASSWORD = "prefirooglide"

# Decorator para verificar autenticação
def login_required(f):
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect('/login')
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

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
    'batch_size': 50,       # Tamanho de cada lote (padrão: 50)
    'total_batches': 0,     # Número total de lotes
    'current_batch': 0,     # Lote atual sendo processado
    'all_batches': [],      # Lista com todos os lotes
    'processed_batches': [], # Lista de lotes já processados e seus resultados
    'job_queue': [],        # Fila de trabalhos pendentes para processamento
    'ignored_urls': set()   # Conjunto de URLs a serem ignoradas no processamento
}

# Carregar URLs ignoradas do banco de dados
def load_ignored_urls():
    """Carrega a lista de URLs ignoradas do banco de dados"""
    global processing_progress
    try:
        with app.app_context():
            ignored_urls = IgnoredURL.query.all()
            processing_progress['ignored_urls'] = set(url.url for url in ignored_urls)
            logger.debug(f"Carregadas {len(processing_progress['ignored_urls'])} URLs ignoradas do banco de dados")
    except Exception as e:
        logger.error(f"Erro ao carregar URLs ignoradas: {str(e)}")

# Carregar lotes processados do banco de dados
def load_processed_batches():
    """Carrega os lotes processados do banco de dados"""
    global processing_progress
    try:
        with app.app_context():
            batches = ProcessedBatch.query.order_by(ProcessedBatch.batch_index).all()
            processing_progress['processed_batches'] = [batch.to_dict() for batch in batches]
            if processing_progress['processed_batches']:
                processing_progress['current_batch'] = max(batch['batch_index'] for batch in processing_progress['processed_batches']) + 1
            logger.debug(f"Carregados {len(processing_progress['processed_batches'])} lotes processados do banco de dados")
    except Exception as e:
        logger.error(f"Erro ao carregar lotes processados: {str(e)}")

# Verificar se o banco de dados está inicializado antes de carregar os dados
try:
    # Carregar dados do banco de dados ao iniciar
    with app.app_context():
        load_ignored_urls()
        load_processed_batches()
except Exception as e:
    logger.error(f"Erro ao carregar dados do banco de dados: {str(e)}")

# Check if Gemini API key is available
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
logger.debug(f"Gemini API Key está disponível: {GEMINI_API_KEY is not None}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Rota de login para autenticação do usuário.
    """
    if request.method == 'POST':
        password = request.form.get('password')
        if password == APP_PASSWORD:
            session['authenticated'] = True
            flash('Login realizado com sucesso!', 'success')
            return redirect('/')
        else:
            flash('Senha incorreta!', 'danger')
    
    return render_template('login.html')

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """
    Home route for the LinkedIn Job Scraper app.
    Handles both GET and POST requests.
    """
    results_html = None
    linkedin_urls_text = ''
    ignore_urls_text = ''
    batch_size = 50
    analyze_jobs_checked = False
    
    # Carregar os inputs salvos do banco de dados
    try:
        with app.app_context():
            user_inputs = UserInputs.get_latest()
            if user_inputs:
                linkedin_urls_text = user_inputs.linkedin_urls or ''
                ignore_urls_text = user_inputs.ignore_urls or ''
                batch_size = user_inputs.batch_size or 50
                analyze_jobs_checked = user_inputs.analyze_jobs or False
    except Exception as e:
        logger.error(f"Erro ao carregar inputs salvos: {str(e)}")
    
    if request.method == 'POST':
        # Get LinkedIn URLs from the form
        linkedin_urls_text = request.form.get('linkedin_urls', '')
        ignore_urls_text = request.form.get('ignore_urls', '')
        batch_size_text = request.form.get('batch_size', '50')
        
        try:
            batch_size = int(batch_size_text)
        except ValueError:
            batch_size = 50
            
        # Check if user wants to analyze jobs with Gemini AI
        analyze_jobs_checked = 'analyze_jobs' in request.form
        
        # Salvar os inputs no banco de dados
        try:
            with app.app_context():
                user_inputs = UserInputs.get_latest()
                user_inputs.update(
                    linkedin_urls=linkedin_urls_text,
                    ignore_urls=ignore_urls_text,
                    batch_size=batch_size,
                    analyze_jobs=analyze_jobs_checked
                )
                logger.debug("Inputs do usuário salvos no banco de dados")
        except Exception as e:
            logger.error(f"Erro ao salvar inputs no banco de dados: {str(e)}")
        
        # Processar os URLs
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
        
        if not linkedin_urls:
            flash('Please enter at least one LinkedIn job URL.', 'danger')
        else:
            # Store the URLs in the session for export functionality
            session['linkedin_urls'] = linkedin_urls
            
            # Process the URLs and get results
            try:
                # Analisar jobs se solicitado e se a API do Gemini estiver disponível
                analyze_jobs = analyze_jobs_checked
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
    
    # Obter lista de lotes processados para exibição
    batches = []
    for i, batch in enumerate(processing_progress['processed_batches']):
        batch_info = {
            'index': batch.get('batch_index', i),
            'count': len(batch.get('urls', [])),
            'has_error': batch.get('has_error', False),
            'created_at': batch.get('created_at', '')
        }
        batches.append(batch_info)
    
    # Obter lista de URLs ignoradas
    ignored_urls = list(processing_progress['ignored_urls'])
    
    return render_template('index.html', 
                          results_html=results_html, 
                          has_results=has_results,
                          gemini_available=gemini_available,
                          batches=batches,
                          ignored_urls=ignored_urls,
                          processing_status=processing_progress['status'],
                          linkedin_urls=linkedin_urls_text,
                          ignore_urls=ignore_urls_text,
                          batch_size=batch_size,
                          analyze_jobs_checked=analyze_jobs_checked)

@app.route('/export/csv', methods=['GET'])
@login_required
def export_csv():
    """
    Exporta os dados de vagas do LinkedIn para CSV.
    Se o parâmetro batch_index for fornecido, exporta apenas os dados do lote específico.
    Se batch_indices for fornecido, exporta múltiplos lotes especificados.
    Caso contrário, exporta todos os dados disponíveis.
    """
    global processing_progress
    batch_index = request.args.get('batch_index')
    batch_indices = request.args.get('batch_indices')
    
    try:
        if batch_indices is not None:
            # Exportar múltiplos lotes específicos
            try:
                # Formato esperado: "0,1,2,3" ou similar
                indices = [int(idx.strip()) for idx in batch_indices.split(',') if idx.strip()]
                if indices:
                    return export_multiple_batches_csv(indices)
                else:
                    flash('Nenhum índice de lote válido fornecido.', 'warning')
                    return redirect('/')
            except ValueError:
                flash('Formato de índices de lotes inválido. Use formato: "0,1,2,3"', 'danger')
                return redirect('/')
        elif batch_index is not None:
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

# Função para exportar múltiplos lotes para CSV
def export_multiple_batches_csv(batch_indices):
    """
    Exporta os dados de múltiplos lotes específicos para um único arquivo CSV.
    
    Args:
        batch_indices (list): Lista de índices dos lotes a serem exportados
        
    Returns:
        Response: Arquivo CSV para download combinado
    """
    global processing_progress
    
    # Verificar se todos os índices são válidos
    invalid_indices = []
    for idx in batch_indices:
        if idx < 0 or idx >= len(processing_progress['processed_batches']):
            invalid_indices.append(idx)
    
    if invalid_indices:
        flash(f'Os seguintes lotes não foram encontrados: {", ".join(map(str, invalid_indices))}', 'danger')
        return redirect('/')
    
    # Coletar dados de todos os lotes solicitados
    all_urls = []
    all_df_jsons = []
    
    for idx in batch_indices:
        batch_data = processing_progress['processed_batches'][idx]
        
        # Verificar se temos dados válidos para este lote
        if not batch_data.get('urls') or not batch_data.get('df_json'):
            continue
        
        all_urls.extend(batch_data['urls'])
        all_df_jsons.append(batch_data['df_json'])
    
    # Verificar se temos dados para exportar
    if not all_urls or not all_df_jsons:
        flash('Nenhum dado válido encontrado nos lotes selecionados.', 'warning')
        return redirect('/')
    
    logger.debug(f"Exportando {len(all_urls)} URLs de {len(batch_indices)} lotes para CSV")
    
    try:
        # Precisamos combinar todos os DataFrames em um único
        import pandas as pd
        import json
        from io import BytesIO
        
        # Converter cada JSON string para DataFrame e concatenar
        dataframes = [pd.DataFrame(json.loads(df_json)) for df_json in all_df_jsons]
        combined_df = pd.concat(dataframes, ignore_index=True)
        
        # Remover duplicatas com base no link
        if 'link' in combined_df.columns:
            before_dedup = len(combined_df)
            combined_df = combined_df.drop_duplicates(subset=['link'])
            after_dedup = len(combined_df)
            
            if before_dedup != after_dedup:
                logger.debug(f"Removidas {before_dedup - after_dedup} linhas duplicadas no CSV combinado")
        
        # Converter para CSV
        csv_buffer = BytesIO()
        combined_df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_buffer.seek(0)
        
        # Gerar nome de arquivo com timestamp e indicação dos lotes
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        lotes_str = '-'.join(str(idx) for idx in sorted(batch_indices))
        filename = f'linkedin_jobs_lotes_{lotes_str}_{timestamp}.csv'
        
        # Enviar o arquivo para o usuário
        return send_file(
            csv_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='text/csv'
        )
    except Exception as e:
        logger.error(f"Erro ao exportar múltiplos lotes para CSV: {str(e)}")
        flash(f'Falha ao exportar os lotes selecionados: {str(e)}', 'danger')
        return redirect('/')

@app.route('/select_batches', methods=['POST'])
@login_required
def select_batches():
    """
    Endpoint para selecionar lotes para exportação.
    Retorna JSON em vez de redirecionar, para ser usado com AJAX.
    """
    batch_indices = request.form.getlist('batch_indices[]')
    
    if not batch_indices:
        return jsonify({
            'success': False,
            'message': 'Por favor, selecione pelo menos um lote para exportar.'
        }), 400
    
    # Converter para inteiros
    try:
        batch_indices = [int(idx) for idx in batch_indices]
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Índices de lote inválidos.'
        }), 400
    
    # Validar se todos os lotes existem
    invalid_indices = []
    for idx in batch_indices:
        if idx < 0 or idx >= len(processing_progress['processed_batches']):
            invalid_indices.append(idx)
    
    if invalid_indices:
        return jsonify({
            'success': False,
            'message': f'Os seguintes lotes não foram encontrados: {", ".join(map(str, invalid_indices))}'
        }), 400
    
    # Tudo bem, retornar sucesso
    indices_string = ",".join(map(str, batch_indices))
    return jsonify({
        'success': True,
        'batch_indices': indices_string,
        'message': f'Selecionados {len(batch_indices)} lotes. Clique em Exportar para baixar.'
    })

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('index.html', error="Server error occurred"), 500

@app.route('/process_async', methods=['POST'])
@login_required
def process_async():
    """
    Processa URLs do LinkedIn de forma assíncrona e atualiza o progresso
    Divide os URLs em lotes para processamento mais rápido e seguro
    Suporta enfileiramento de trabalhos quando já há um processamento em andamento
    """
    global processing_progress
    
    # Log da solicitação para depuração
    logger.debug(f"Solicitação de processamento assíncrono recebida: {request.form}")
    
    try:
        # Obter URLs do formulário
        linkedin_urls_text = request.form.get('linkedin_urls', '')
        ignore_urls_text = request.form.get('ignore_urls', '')
        batch_size_text = request.form.get('batch_size', '10')
        
        # Converter o tamanho do lote para inteiro
        try:
            batch_size = int(batch_size_text)
            processing_progress['batch_size'] = batch_size
        except ValueError:
            logger.warning(f"Valor inválido para batch_size: {batch_size_text}, usando padrão 50")
            batch_size = 50
            processing_progress['batch_size'] = batch_size
            
        # Verificar se usuário quer analisar jobs com Gemini AI
        analyze_jobs = 'analyze_jobs' in request.form
        
        # Salvar os inputs no banco de dados
        try:
            with app.app_context():
                user_inputs = UserInputs.get_latest()
                user_inputs.update(
                    linkedin_urls=linkedin_urls_text,
                    ignore_urls=ignore_urls_text,
                    batch_size=batch_size,
                    analyze_jobs=analyze_jobs
                )
                logger.debug("Inputs do usuário salvos no banco de dados")
        except Exception as e:
            logger.error(f"Erro ao salvar inputs no banco de dados: {str(e)}")
        
        # Processar URLs a serem ignoradas e salvá-las no banco de dados
        ignore_urls = [url.strip() for url in ignore_urls_text.split('\n') if url.strip()]
        if ignore_urls:
            # Atualizar o conjunto de URLs a serem ignoradas
            processing_progress['ignored_urls'].update(ignore_urls)
            logger.debug(f"Adicionadas {len(ignore_urls)} URLs à lista de ignorados")
            
            # Salvar no banco de dados
            try:
                with app.app_context():
                    for url in ignore_urls:
                        # Verificar se já existe
                        existing = IgnoredURL.query.filter_by(url=url).first()
                        if not existing:
                            new_url = IgnoredURL(url=url)
                            db.session.add(new_url)
                    db.session.commit()
                    logger.debug(f"URLs ignoradas salvas no banco de dados")
            except Exception as e:
                logger.error(f"Erro ao salvar URLs ignoradas no banco de dados: {str(e)}")
        
        # Processar URLs a serem analisadas
        linkedin_urls_raw = [url.strip() for url in linkedin_urls_text.split('\n') if url.strip()]
        
        # Remover duplicatas mantendo a ordem original
        linkedin_urls = []
        seen_urls = set()
        for url in linkedin_urls_raw:
            if url not in seen_urls and url not in processing_progress['ignored_urls']:
                linkedin_urls.append(url)
                seen_urls.add(url)
        
        if not linkedin_urls:
            return jsonify({
                'success': False,
                'message': 'Por favor, forneça pelo menos um URL válido do LinkedIn que não esteja na lista de ignorados.'
            })
        
        # Verificar se usuário quer analisar jobs com Gemini AI
        if analyze_jobs and not GEMINI_API_KEY:
            logger.warning('Análise com Gemini AI solicitada, mas a chave de API não está disponível.')
            analyze_jobs = False
        
        # Dividir URLs em lotes conforme o tamanho configurado
        batches = [linkedin_urls[i:i+batch_size] for i in range(0, len(linkedin_urls), batch_size)]
        
        logger.debug(f"URLs divididos em {len(batches)} lotes de até {batch_size} cada")
        
        # Verificar se já existe um processamento em andamento
        if processing_progress['status'] == 'processing':
            # Adicionar novo trabalho à fila
            new_job = {
                'batches': batches,
                'analyze_jobs': analyze_jobs
            }
            processing_progress['job_queue'].append(new_job)
            logger.debug(f"Processamento já em andamento. Trabalho adicionado à fila. Fila atual: {len(processing_progress['job_queue'])}")
            return jsonify({
                'success': True,
                'message': 'Processamento já em andamento. Sua solicitação foi adicionada à fila e será processada em seguida.',
                'queue_position': len(processing_progress['job_queue'])
            })
        else:
            # Iniciar novo processamento
            processing_progress['status'] = 'processing'
            processing_progress['all_batches'] = batches
            processing_progress['total_batches'] = len(batches)
            processing_progress['analyze_jobs'] = analyze_jobs
            
            # Iniciar o processamento em uma thread separada
            thread = threading.Thread(target=process_batches_background, args=(batches, analyze_jobs))
            thread.daemon = True
            thread.start()
            
            logger.debug(f"Iniciado processamento assíncrono com {len(batches)} lotes")
            return jsonify({
                'success': True,
                'message': f'Iniciado processamento assíncrono de {len(linkedin_urls)} URLs em {len(batches)} lotes.',
                'batch_count': len(batches)
            })
    
    except Exception as e:
        logger.error(f"Erro ao processar solicitação assíncrona: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro ao processar solicitação: {str(e)}'
        }), 500

def update_progress(current, total, message):
    """
    Callback para atualizar o progresso do processamento
    """
    global processing_progress
    processing_progress['current'] = current
    processing_progress['total'] = total
    processing_progress['message'] = message
    logger.debug(f"Progresso atualizado: {current}/{total} - {message}")

def process_batches_background(batches, analyze_jobs=False):
    """
    Processa lotes de URLs sequencialmente
    
    Args:
        batches (list): Lista de lotes, cada lote é uma lista de URLs
        analyze_jobs (bool): Se True, analisa as vagas com a API Gemini
    """
    global processing_progress
    
    processing_progress['status'] = 'processing'
    processing_progress['current_batch'] = 0
    processing_progress['total_batches'] = len(batches)
    processing_progress['analyze_jobs'] = analyze_jobs
    
    try:
        # Processar cada lote sequencialmente
        for i, batch_urls in enumerate(batches):
            batch_index = i
            
            # Verificar se este lote já foi processado e salvo no banco de dados
            with app.app_context():
                existing_batch = ProcessedBatch.query.filter_by(batch_index=batch_index).first()
                if existing_batch and existing_batch.df_json:
                    # Adicionar à lista de lotes processados
                    batch_data = existing_batch.to_dict()
                    
                    # Atualizar lista de lotes processados se necessário
                    found = False
                    for j, existing in enumerate(processing_progress['processed_batches']):
                        if existing.get('batch_index') == batch_index:
                            processing_progress['processed_batches'][j] = batch_data
                            found = True
                            break
                    
                    if not found:
                        processing_progress['processed_batches'].append(batch_data)
                    
                    logger.debug(f"Lote {batch_index} já existe no banco de dados, pulando processamento")
                    continue
            
            # Atualizar informações de progresso para este lote
            processing_progress['current_batch'] = batch_index
            processing_progress['message'] = f'Processando lote {batch_index+1} de {len(batches)}'
            
            # Definir callback para atualizar o progresso dentro deste lote
            def batch_progress_callback(current, total, message):
                update_progress(current, total, f"Lote {batch_index+1}/{len(batches)}: {message}")
            
            logger.debug(f"Iniciando processamento do lote {batch_index} com {len(batch_urls)} URLs")
            
            # Executar o processamento deste lote
            try:
                results_html, df_export = get_results_html(
                    batch_urls, 
                    analyze_jobs=analyze_jobs, 
                    progress_callback=batch_progress_callback
                )
                
                # Salvar resultados
                batch_success = True
                batch_error = None
                df_json = None
                
                if df_export is not None:
                    # Converter DataFrame para JSON
                    df_json = df_export.to_json(orient='records')
                    logger.debug(f"DataFrame do lote {batch_index} gerado com {len(df_export)} registros")
            except Exception as e:
                logger.error(f"Erro ao processar lote {batch_index}: {str(e)}")
                results_html = f"<div class='alert alert-danger'>Erro ao processar lote {batch_index}: {str(e)}</div>"
                batch_success = False
                batch_error = str(e)
                df_json = None
            
            # Adicionar resultados deste lote à lista de lotes processados
            batch_data = {
                'batch_index': batch_index,
                'urls': batch_urls,
                'results_html': results_html,
                'df_json': df_json,
                'has_error': not batch_success,
                'error': batch_error
            }
            
            # Atualizar lista de lotes processados
            found = False
            for j, existing in enumerate(processing_progress['processed_batches']):
                if existing.get('batch_index') == batch_index:
                    processing_progress['processed_batches'][j] = batch_data
                    found = True
                    break
            
            if not found:
                processing_progress['processed_batches'].append(batch_data)
            
            # Salvar no banco de dados
            try:
                with app.app_context():
                    # Verificar novamente se já existe (para evitar concorrência)
                    existing_batch = ProcessedBatch.query.filter_by(batch_index=batch_index).first()
                    if existing_batch:
                        # Atualizar
                        existing_batch.urls = json.dumps(batch_urls)
                        existing_batch.results_html = results_html
                        existing_batch.df_json = df_json
                        existing_batch.has_error = not batch_success
                    else:
                        # Criar novo
                        new_batch = ProcessedBatch(
                            batch_index=batch_index,
                            urls=json.dumps(batch_urls),
                            results_html=results_html,
                            df_json=df_json,
                            has_error=not batch_success
                        )
                        db.session.add(new_batch)
                    
                    db.session.commit()
                    logger.debug(f"Lote {batch_index} salvo no banco de dados com sucesso")
            except Exception as e:
                logger.error(f"Erro ao salvar lote {batch_index} no banco de dados: {str(e)}")
        
        # Finalizar processamento
        processing_progress['status'] = 'completed'
        processing_progress['message'] = 'Processamento de todos os lotes concluído!'
        logger.debug("Processamento em lotes concluído com sucesso")
        
        # Verificar se há mais trabalhos na fila
        if processing_progress['job_queue']:
            logger.debug(f"Há {len(processing_progress['job_queue'])} trabalhos na fila. Processando o próximo...")
            next_job = processing_progress['job_queue'].pop(0)
            
            # Iniciar processamento do próximo trabalho
            thread = threading.Thread(
                target=process_batches_background, 
                args=(next_job['batches'], next_job['analyze_jobs'])
            )
            thread.daemon = True
            thread.start()
        
    except Exception as e:
        logger.error(f"Erro durante o processamento em lotes: {str(e)}")
        processing_progress['status'] = 'error'
        processing_progress['message'] = f'Erro: {str(e)}'

@app.route('/reset_processing', methods=['POST'])
@login_required
def reset_processing():
    """
    Reinicia o status de processamento em caso de travamento.
    """
    global processing_progress
    
    # Salvar estado atual para logging
    old_status = processing_progress['status']
    job_queue_count = len(processing_progress['job_queue'])
    
    # Reiniciar variáveis de progresso
    processing_progress['status'] = 'idle'
    processing_progress['message'] = 'Processamento reiniciado'
    processing_progress['job_queue'] = []
    
    logger.warning(f"Processamento reiniciado manualmente. Status anterior: {old_status}, Jobs na fila: {job_queue_count}")
    
    # Retornar resposta
    return jsonify({
        'success': True,
        'message': 'Processamento reiniciado com sucesso. Você pode iniciar um novo processamento agora.'
    })

@app.route('/check_progress', methods=['GET'])
@login_required
def check_progress():
    """
    Retorna o status atual do processamento
    """
    global processing_progress
    
    # Calcular percentuais para as barras de progresso
    current = processing_progress['current']
    total = processing_progress['total']
    percent = 0
    if total > 0:
        percent = int((current / total) * 100)
    
    current_batch = processing_progress['current_batch']
    total_batches = processing_progress['total_batches'] 
    batch_percent = 0
    if total_batches > 0:
        batch_percent = int((current_batch / total_batches) * 100)
    
    # Preparar resposta com informações relevantes sobre o progresso
    response = {
        'status': processing_progress['status'],
        'message': processing_progress['message'],
        'current': current,
        'total': total,
        'percent': percent,
        'current_batch': current_batch,
        'total_batches': total_batches,
        'batch_percent': batch_percent,
        'processed_batches': len(processing_progress['processed_batches']),
        'job_queue': len(processing_progress['job_queue']),
        'results': None
    }
    
    # Se o processamento estiver concluído, incluir resultados
    if processing_progress['status'] == 'completed' and processing_progress['results']:
        response['results'] = processing_progress['results']
    
    # Incluir informações detalhadas sobre lotes processados
    response['batches'] = []
    response['batches_info'] = []
    for batch in processing_progress['processed_batches']:
        # Versão simplificada para compatibilidade
        response['batches'].append({
            'batch_index': batch.get('batch_index'),
            'urls_count': len(batch.get('urls', [])),
            'has_error': batch.get('has_error', False)
        })
        
        # Versão completa para a nova interface
        response['batches_info'].append({
            'batch_index': batch.get('batch_index'),
            'urls_count': len(batch.get('urls', [])),
            'has_error': batch.get('has_error', False),
            'created_at': batch.get('created_at', '')
        })
    
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)