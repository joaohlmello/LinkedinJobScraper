import os
import logging
import json
import io
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from models import db, ProcessedBatch, IgnoredURL

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Criar aplicação Flask
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "a secret key"

# Configurar banco de dados
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Criar tabelas do banco de dados
with app.app_context():
    db.create_all()
    logger.debug("Tabelas do banco de dados criadas/verificadas")

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
            
            # Extrair primeiro resultado do primeiro lote se disponível
            if batches and batches[0].df_json:
                try:
                    import pandas as pd
                    import json
                    import re
                    
                    # Tentar carregar o DataFrame do primeiro lote
                    df_json = batches[0].df_json
                    df = pd.read_json(df_json)
                    
                    if not df.empty:
                        # Converter a primeira linha para um dicionário
                        first_result = df.iloc[0].to_dict()
                        # Remover formatação HTML da descrição
                        if 'job_description' in first_result:
                            first_result['job_description'] = first_result['job_description'].replace('<br><br>', '\n\n').replace('<br>', '\n')
                        # Remover HTML dos links
                        for field in ['link', 'company_link']:
                            if field in first_result and isinstance(first_result[field], str) and '<a href=' in first_result[field]:
                                url_match = re.search(r'href="([^"]+)"', first_result[field])
                                if url_match:
                                    first_result[field] = url_match.group(1)
                        
                        # Armazenar o primeiro resultado para exibição
                        processing_progress['first_result'] = first_result
                except Exception as e:
                    logger.error(f"Erro ao extrair primeiro resultado: {str(e)}")
                    processing_progress['first_result'] = None
            else:
                processing_progress['first_result'] = None
                
            logger.debug(f"Carregados {len(processing_progress['processed_batches'])} lotes processados do banco de dados")
    except Exception as e:
        logger.error(f"Erro ao carregar lotes processados: {str(e)}")
        processing_progress['first_result'] = None

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

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Home route for the LinkedIn Job Scraper app.
    Handles both GET and POST requests.
    """
    results_html = None
    first_result = processing_progress.get('first_result')
    
    if first_result:
        logger.debug(f"Primeiro resultado encontrado: {first_result.get('job_title', 'N/A')}")
    else:
        logger.debug("Nenhum primeiro resultado encontrado")
    
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
            flash(f"{duplicates_removed} URLs duplicados foram removidos.", "info")
        
        # Get ignore URLs from the form
        ignore_urls_text = request.form.get('ignore_urls', '')
        ignore_urls = [url.strip() for url in ignore_urls_text.split('\n') if url.strip()]
        
        # Adicionar URLs ignoradas ao banco de dados
        if ignore_urls:
            try:
                with app.app_context():
                    for url in ignore_urls:
                        # Verificar se já existe
                        existing = IgnoredURL.query.filter_by(url=url).first()
                        if not existing:
                            ignored_url = IgnoredURL(url=url)
                            db.session.add(ignored_url)
                    db.session.commit()
                    # Recarregar a lista atual
                    load_ignored_urls()
            except Exception as e:
                logger.error(f"Erro ao adicionar URLs ignoradas: {str(e)}")
        
        # Process the URLs if any are provided
        if linkedin_urls:
            # Verificar se já há processamento em andamento
            is_processing = processing_progress['status'] == 'processing'
            if is_processing:
                # Adicionar à fila de trabalhos pendentes
                batch_size = int(request.form.get('batch_size', '10'))
                analyze_jobs = 'analyze_jobs' in request.form
                
                # Adicionar trabalhos à fila
                processing_progress['job_queue'].append({
                    'urls': linkedin_urls,
                    'batch_size': batch_size,
                    'analyze_jobs': analyze_jobs
                })
                
                flash("Solicitação adicionada à fila. Será processada após a conclusão do trabalho atual.", "info")
                logger.info(f"Nova solicitação adicionada à fila. Total na fila: {len(processing_progress['job_queue'])}")
            else:
                # Iniciar processamento assíncrono e exibir mensagem de progresso
                flash("Processamento iniciado. Consulte o status abaixo para acompanhar o progresso.", "success")
                # Disparar processamento assíncrono
                batch_size = int(request.form.get('batch_size', '10'))
                analyze_jobs = 'analyze_jobs' in request.form
                logger.debug(f"Solicitação de processamento assíncrono recebida: {request.form}")
                
                # Limpar resultados anteriores somente se não houver trabalhos na fila
                if not processing_progress['job_queue']:
                    processing_progress['results'] = None
                    
                from threading import Thread
                thread = Thread(target=process_async, args=(linkedin_urls, batch_size, analyze_jobs))
                thread.daemon = True
                thread.start()
        else:
            flash("Por favor, insira ao menos uma URL do LinkedIn.", "warning")
    
    # Check if we have results to display
    has_results = processing_progress.get('results') is not None
    has_processed_batches = len(processing_progress.get('processed_batches', [])) > 0
    
    if has_results:
        results_html = processing_progress['results']
    
    # Check if Gemini API is available
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
    
    # Passar o primeiro resultado para o template
    first_result = processing_progress.get('first_result')
    
    if first_result:
        logger.debug(f"Primeiro resultado encontrado: {first_result.get('job_title', 'N/A')}")
    else:
        logger.debug("Nenhum primeiro resultado encontrado")
    
    return render_template('index.html', 
                          results_html=results_html, 
                          has_results=has_results,
                          has_processed_batches=has_processed_batches,
                          gemini_available=gemini_available,
                          batches=batches,
                          ignored_urls=ignored_urls,
                          processing_status=processing_progress['status'],
                          first_result=first_result)

@app.route('/export/csv', methods=['GET'])
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
    
    if batch_index is not None:
        try:
            return export_batch_csv(int(batch_index))
        except Exception as e:
            flash(f"Erro ao exportar lote {batch_index}: {str(e)}", "danger")
            return redirect(url_for('index'))
    elif batch_indices is not None:
        try:
            # Converter string de índices para lista de inteiros
            indices = [int(idx.strip()) for idx in batch_indices.split(',') if idx.strip()]
            return export_multiple_batches_csv(indices)
        except Exception as e:
            flash(f"Erro ao exportar lotes selecionados: {str(e)}", "danger")
            return redirect(url_for('index'))
    else:
        try:
            return export_all_csv()
        except Exception as e:
            flash(f"Erro ao exportar dados: {str(e)}", "danger")
            return redirect(url_for('index'))

@app.route('/export/all/csv', methods=['GET'])
def export_all_csv():
    """
    Exporta todos os dados de vagas do LinkedIn para CSV.
    """
    global processing_progress
    logger.debug("Solicitação de exportação CSV para todos os lotes")
    
    try:
        # Verificar se há lotes processados
        if not processing_progress['processed_batches']:
            flash("Não há dados para exportar.", "warning")
            return redirect(url_for('index'))
        
        # Usar o último lote processado como base para a exportação
        all_batches_urls = []
        for batch in processing_progress['processed_batches']:
            # Adicionar URLs deste lote
            all_batches_urls.extend(batch.get('urls', []))
        
        # Usar a função de exportação da biblioteca linkedin_scraper
        from linkedin_scraper import export_to_csv
        
        # Criar o buffer CSV
        csv_buffer = export_to_csv(all_batches_urls)
        
        # Enviar o arquivo para download
        return send_file(
            io.BytesIO(csv_buffer.getvalue()), 
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"linkedin_jobs_all_batches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
    except Exception as e:
        logger.error(f"Erro ao exportar todos os lotes para CSV: {str(e)}")
        flash(f"Erro na exportação: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/export/batch/<int:batch_index>/csv', methods=['GET'])
def export_batch_csv(batch_index):
    """
    Exporta os dados de um lote específico para CSV.
    
    Args:
        batch_index (int): Índice do lote a ser exportado
    
    Returns:
        Response: Arquivo CSV para download
    """
    global processing_progress
    logger.debug(f"Exportando lote {batch_index} com {len(processing_progress['processed_batches'])} lotes processados")
    
    try:
        # Encontrar o lote específico
        batch = None
        for b in processing_progress['processed_batches']:
            if b.get('batch_index') == batch_index:
                batch = b
                break
        
        if not batch:
            flash(f"Lote {batch_index} não encontrado.", "warning")
            return redirect(url_for('index'))
        
        # Usar a função de exportação da biblioteca linkedin_scraper
        from linkedin_scraper import export_to_csv
        
        # Criar o buffer CSV usando os dados pré-processados
        df_json = batch.get('df_json')
        
        if df_json:
            # Se temos dados JSON pré-processados, usar para exportação
            csv_buffer = export_to_csv(batch.get('urls', []), df_json=df_json)
        else:
            # Caso contrário, tentar processar novamente (menos eficiente)
            csv_buffer = export_to_csv(batch.get('urls', []))
        
        # Enviar o arquivo para download
        return send_file(
            io.BytesIO(csv_buffer.getvalue()), 
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"linkedin_jobs_batch_{batch_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
    except Exception as e:
        logger.error(f"Erro ao exportar lote {batch_index} para CSV: {str(e)}")
        flash(f"Erro na exportação do lote {batch_index}: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/export/multiple_batches/csv', methods=['POST'])
def export_multiple_batches_csv(batch_indices):
    """
    Exporta os dados de múltiplos lotes específicos para um único arquivo CSV.
    
    Args:
        batch_indices (list): Lista de índices dos lotes a serem exportados
        
    Returns:
        Response: Arquivo CSV para download combinado
    """
    global processing_progress
    logger.debug(f"Exportando múltiplos lotes: {batch_indices}")
    
    try:
        # Obter dados de todos os lotes selecionados
        selected_batches = []
        
        for idx in batch_indices:
            for batch in processing_progress['processed_batches']:
                if batch.get('batch_index') == idx:
                    selected_batches.append(batch)
                    break
        
        if not selected_batches:
            flash("Nenhum dos lotes selecionados foi encontrado.", "warning")
            return redirect(url_for('index'))
        
        # Combinar todas as URLs de todos os lotes selecionados
        all_urls = []
        all_df_json = []
        
        for batch in selected_batches:
            all_urls.extend(batch.get('urls', []))
            if batch.get('df_json'):
                all_df_json.append(batch.get('df_json'))
        
        # Usar a função de exportação da biblioteca linkedin_scraper
        from linkedin_scraper import export_to_csv
        
        # Se tivermos dados JSON pré-processados de todos os lotes, combiná-los
        combined_df_json = None
        if all_df_json and len(all_df_json) == len(selected_batches):
            # Combinar os dataframes
            import pandas as pd
            import json
            from io import StringIO
            
            dfs = []
            for df_str in all_df_json:
                try:
                    df = pd.read_json(df_str)
                    dfs.append(df)
                except:
                    # Se houver erro, ignorar este lote para o JSON combinado
                    logger.warning("Erro ao processar um dos DataFrames JSON. Usando método alternativo.")
                    combined_df_json = None
                    break
            
            if dfs:
                try:
                    # Concatenar todos os DataFrames
                    combined_df = pd.concat(dfs, ignore_index=True)
                    # Converter de volta para JSON
                    combined_df_json = combined_df.to_json()
                except Exception as e:
                    logger.warning(f"Erro ao combinar DataFrames: {str(e)}")
                    combined_df_json = None
        
        # Criar o buffer CSV
        if combined_df_json:
            csv_buffer = export_to_csv(all_urls, df_json=combined_df_json)
        else:
            # Caso contrário, tentar processar novamente (menos eficiente)
            csv_buffer = export_to_csv(all_urls)
        
        # Enviar o arquivo para download
        batch_str = "_".join([str(idx) for idx in batch_indices])
        return send_file(
            io.BytesIO(csv_buffer.getvalue()), 
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"linkedin_jobs_batches_{batch_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
    except Exception as e:
        logger.error(f"Erro ao exportar múltiplos lotes para CSV: {str(e)}")
        flash(f"Erro na exportação de múltiplos lotes: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/select_batches', methods=['POST'])
def select_batches():
    """
    Endpoint para selecionar lotes para exportação.
    Retorna JSON em vez de redirecionar, para ser usado com AJAX.
    """
    selected_indices = request.form.getlist('batch_indices')
    
    if not selected_indices:
        return jsonify({
            'status': 'error',
            'message': 'Nenhum lote selecionado'
        }), 400
    
    # Converter para números inteiros
    try:
        indices = [int(idx) for idx in selected_indices]
        indices_str = ','.join(selected_indices)
        
        return jsonify({
            'status': 'success',
            'message': f'{len(indices)} lotes selecionados',
            'url': url_for('export_csv', batch_indices=indices_str)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Erro ao processar índices: {str(e)}'
        }), 400

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return render_template('500.html'), 500

def process_async(urls, batch_size=10, analyze_jobs=False):
    """
    Processa URLs do LinkedIn de forma assíncrona e atualiza o progresso
    Divide os URLs em lotes para processamento mais rápido e seguro
    Suporta enfileiramento de trabalhos quando já há um processamento em andamento
    """
    global processing_progress
    
    # Inicializar variáveis de progresso
    processing_progress['status'] = 'processing'
    processing_progress['urls'] = urls
    processing_progress['batch_size'] = batch_size
    processing_progress['analyze_jobs'] = analyze_jobs
    
    try:
        # Dividir URLs em lotes do tamanho especificado
        batches = []
        for i in range(0, len(urls), batch_size):
            batches.append(urls[i:i+batch_size])
        
        # Atualizar informações de lotes
        processing_progress['all_batches'] = batches
        processing_progress['total_batches'] = len(batches)
        
        logger.info(f"Iniciando processamento assíncrono com {len(batches)} lotes")
        
        # Processar os lotes sequencialmente
        process_batches_background(batches, analyze_jobs)
        
        # Verificar se há trabalhos na fila após concluir o atual
        if processing_progress['job_queue']:
            # Obter o próximo trabalho da fila
            next_job = processing_progress['job_queue'].pop(0)
            
            # Iniciar novo processamento com o próximo trabalho
            process_async(
                next_job['urls'], 
                next_job.get('batch_size', 10), 
                next_job.get('analyze_jobs', False)
            )
        else:
            # Se não houver mais trabalhos, marcar como concluído
            processing_progress['status'] = 'completed'
            processing_progress['message'] = 'Processamento concluído com sucesso!'
    
    except Exception as e:
        logger.error(f"Erro no processamento assíncrono: {str(e)}")
        processing_progress['status'] = 'error'
        processing_progress['message'] = f"Erro no processamento: {str(e)}"

def update_progress(current, total, message):
    """
    Callback para atualizar o progresso do processamento
    """
    global processing_progress
    
    processing_progress['current'] = current
    processing_progress['total'] = total
    processing_progress['message'] = message
    
    # Calcular porcentagem
    percent = int((current / total) * 100) if total > 0 else 0
    logger.debug(f"Progresso atualizado: {current}/{total} - {message}")

def process_batches_background(batches, analyze_jobs=False):
    """
    Processa lotes de URLs sequencialmente
    
    Args:
        batches (list): Lista de lotes, cada lote é uma lista de URLs
        analyze_jobs (bool): Se True, analisa as vagas com a API Gemini
    """
    global processing_progress
    
    for i, batch in enumerate(batches):
        try:
            logger.debug(f"Iniciando processamento do lote {i} com {len(batch)} URLs")
            
            # Verificar se há URLs para ignorar
            to_process = []
            for url in batch:
                if url not in processing_progress['ignored_urls']:
                    to_process.append(url)
                
            batch = to_process
            
            if not batch:
                logger.debug(f"Lote {i} vazio ou todas as URLs ignoradas")
                continue
            
            # Processar o lote atual
            batch_index = processing_progress['current_batch'] + i
            
            # Função de callback para acompanhar o progresso do lote
            def batch_progress_callback(current, total, message):
                # Calcular progresso global levando em conta o lote atual
                global_current = (i * processing_progress['batch_size']) + current
                global_total = len(processing_progress['urls'])
                global_message = f"Lote {i+1}/{len(batches)}: {message}"
                
                # Atualizar o progresso global
                update_progress(global_current, global_total, global_message)
            
            # Processar o lote com a biblioteca de scraping
            from linkedin_scraper import get_results_html
            
            # Processar o lote e obter os resultados
            results_html, df_json = get_results_html(
                batch, 
                analyze_jobs=analyze_jobs,
                progress_callback=batch_progress_callback
            )
            
            # Salvar o resultado do lote no banco de dados
            with app.app_context():
                batch_data = ProcessedBatch(
                    batch_index=batch_index,
                    urls=json.dumps(batch),
                    results_html=results_html,
                    df_json=df_json,
                    has_error=False,
                    created_at=datetime.utcnow()
                )
                db.session.add(batch_data)
                db.session.commit()
                
                logger.debug(f"Lote {batch_index} salvo no banco de dados com sucesso")
                
                # Recarregar lotes processados
                processing_progress['processed_batches'] = [b.to_dict() for b in ProcessedBatch.query.order_by(ProcessedBatch.batch_index).all()]
                
                # Extrair primeiro resultado do primeiro lote se disponível
                if batch_index == 0 or not processing_progress.get('first_result'):
                    try:
                        # Tentar carregar o DataFrame do lote
                        df = pd.read_json(df_json)
                        
                        if not df.empty:
                            # Converter a primeira linha para um dicionário
                            first_result = df.iloc[0].to_dict()
                            # Remover formatação HTML da descrição
                            if 'job_description' in first_result:
                                first_result['job_description'] = first_result['job_description'].replace('<br><br>', '\n\n').replace('<br>', '\n')
                            # Remover HTML dos links
                            for field in ['link', 'company_link']:
                                if field in first_result and isinstance(first_result[field], str) and '<a href=' in first_result[field]:
                                    url_match = re.search(r'href="([^"]+)"', first_result[field])
                                    if url_match:
                                        first_result[field] = url_match.group(1)
                                        
                            # Armazenar o primeiro resultado para exibição
                            processing_progress['first_result'] = first_result
                    except Exception as e:
                        logger.error(f"Erro ao extrair primeiro resultado do lote {batch_index}: {str(e)}")
            
            # Atualizar resultados para exibição (mostrando o último lote processado)
            processing_progress['results'] = results_html
            processing_progress['df_json'] = df_json
            
            logger.debug(f"DataFrame do lote {i} gerado com {len(batch)} registros")
            
        except Exception as e:
            logger.error(f"Erro no processamento do lote {i}: {str(e)}")
            
            # Salvar informação de erro no banco de dados
            with app.app_context():
                batch_index = processing_progress['current_batch'] + i
                batch_data = ProcessedBatch(
                    batch_index=batch_index,
                    urls=json.dumps(batch),
                    results_html=f"<div class='alert alert-danger'>Erro no processamento do lote {i}: {str(e)}</div>",
                    df_json=None,
                    has_error=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(batch_data)
                db.session.commit()
    
    # Atualizar índice do lote atual para o próximo processamento
    processing_progress['current_batch'] += len(batches)
    logger.info(f"Processamento em lotes concluído com sucesso")

@app.route('/clear_history', methods=['POST'])
def clear_history():
    """
    Limpa o histórico de processamento, removendo todos os lotes processados do banco de dados
    """
    global processing_progress
    
    try:
        with app.app_context():
            # Remover todos os registros da tabela ProcessedBatch
            ProcessedBatch.query.delete()
            db.session.commit()
            
            # Limpar a lista de lotes processados no objeto de progresso
            processing_progress['processed_batches'] = []
            processing_progress['first_result'] = None
            processing_progress['results'] = None
            
            flash("Histórico de processamento limpo com sucesso!", "success")
    except Exception as e:
        logger.error(f"Erro ao limpar histórico: {str(e)}")
        flash(f"Erro ao limpar histórico: {str(e)}", "danger")
    
    return redirect(url_for('index'))

@app.route('/check_progress', methods=['GET'])
def check_progress():
    """
    Retorna o status atual do processamento
    """
    global processing_progress
    
    # Calcular a porcentagem de progresso
    percent = 0
    if processing_progress['total'] > 0:
        percent = int((processing_progress['current'] / processing_progress['total']) * 100)
    
    return jsonify({
        'status': processing_progress['status'],
        'message': processing_progress['message'],
        'current': processing_progress['current'],
        'total': processing_progress['total'],
        'percent': percent,
        'has_results': processing_progress['results'] is not None,
        'queue_size': len(processing_progress['job_queue'])
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
