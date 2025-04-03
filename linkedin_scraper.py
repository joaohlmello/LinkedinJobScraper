import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import trafilatura
import os
import datetime
import csv
import time
from io import BytesIO
from requests_html import HTMLSession
import re
import openpyxl
from openpyxl.styles import Alignment
from linkedin_login import LinkedInSession
import threading
import queue

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Variável global para armazenar a sessão do LinkedIn
linkedin_session = None
linkedin_session_lock = threading.Lock()

# Fila para armazenar resultados de tipos de candidatura
application_type_queue = queue.Queue()

def get_linkedin_session():
    """
    Retorna uma instância da sessão do LinkedIn, criando-a se necessário.
    
    Returns:
        LinkedInSession: Uma instância da sessão do LinkedIn
    """
    global linkedin_session
    with linkedin_session_lock:
        if linkedin_session is None:
            logger.info("Criando nova sessão do LinkedIn")
            linkedin_session = LinkedInSession(headless=True)
        return linkedin_session

def get_application_type_without_login(job_url, html_content):
    """
    Obtém o tipo de candidatura de uma vaga do LinkedIn sem login, baseado apenas no conteúdo HTML.
    Este é um método menos preciso, mas serve como fallback quando o Selenium não está disponível.
    
    Args:
        job_url (str): URL da vaga no LinkedIn
        html_content (str): Conteúdo HTML da página
        
    Returns:
        str: Tipo de candidatura detectado
    """
    logger.info(f"Detectando tipo de candidatura sem login para: {job_url}")
    application_type = "Apply"  # Valor padrão
    
    # Verificar se é uma URL brasileira ou internacional
    is_brazilian = '.com.br' in job_url or 'br.' in job_url or '.mx' in job_url or 'mx.linkedin' in job_url or '.lat' in job_url
    
    # Procurar por indicadores de "Easy Apply" no HTML
    html_lower = html_content.lower()
    
    # Lista de possíveis indicadores de "Easy Apply" no HTML
    easy_apply_indicators = [
        "easy apply", 
        "candidatura simplificada",
        "candidatura facilitada",
        "candidatar",
        "aplicar fácilmente",
        "aplicar fácil",
        "candidatura fácil",
        "class=\"jobs-apply-button",
        "data-control-name=\"jobdetails_topcard_inapply\"",
        "artdeco-inline-feedback",
        "jobs-s-apply"
    ]
    
    # Primeiro check: procurar padrões no HTML completo
    for indicator in easy_apply_indicators:
        if indicator in html_lower:
            logger.info(f"Indicador de Easy Apply encontrado: '{indicator}'")
            application_type = "Easy Apply"
            break
    
    # Segundo check: procurar por botões específicos via BeautifulSoup
    if application_type == "Apply":
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Buscar botões e elementos específicos que indicam Easy Apply
            apply_buttons = soup.select('.jobs-apply-button, [data-control-name*="apply"], [data-tracking-control-name*="apply"]')
            for button in apply_buttons:
                button_text = button.get_text(strip=True).lower()
                
                # Verificar se o texto do botão contém indicadores de Easy Apply
                if any(indicator in button_text for indicator in easy_apply_indicators):
                    logger.info(f"Easy Apply detectado em botão para URL: {job_url}")
                    application_type = "Easy Apply"
                    break
                
                # Verificar classes e atributos do botão
                for attr_name, attr_value in button.attrs.items():
                    if isinstance(attr_value, str) and any(indicator in attr_value.lower() for indicator in easy_apply_indicators):
                        logger.info(f"Easy Apply detectado em atributo {attr_name} para URL: {job_url}")
                        application_type = "Easy Apply"
                        break
                    
                # Se é URL brasileira e botão contém "Candidatar"
                if is_brazilian and 'candidatar' in button_text:
                    logger.info(f"Provável Easy Apply em botão brasileiro para URL: {job_url}")
                    application_type = "Easy Apply (detectado sem login)"
                    break
                    
            # Verificar links específicos para Apply offsite
            if application_type == "Apply":
                apply_offsite_links = soup.select('a[data-tracking-control-name*="public_jobs_apply-link-offsite"]')
                if apply_offsite_links:
                    logger.info(f"Link externo (Apply) detectado para URL: {job_url}")
                    # Aqui mantemos como "Apply" pois é definitivamente externo
                
                # Verificar texto indicando que a candidatura será em outro site
                offsite_indicators = [
                    'candidature-se no site da empresa',
                    'apply on company website', 
                    'aplicar no site da empresa',
                    'redirect to company website'
                ]
                
                for text in offsite_indicators:
                    if text in html_lower:
                        logger.info(f"Indicador de site externo (Apply) detectado para URL: {job_url}")
                        # Confirmado como "Apply" externo
                        break
        
        except Exception as e:
            logger.error(f"Erro ao analisar HTML para detecção de tipo de candidatura: {str(e)}")
    
    # Para URLs do LinkedIn Brasil ou LATAM, adicionar indicador
    if application_type == "Apply" and is_brazilian:
        logger.info("URL do LinkedIn Brasil/LATAM detectada, marcando como potencial Easy Apply")
        application_type = "Apply (possível Easy Apply*)"
    
    return application_type

def get_application_type_logged_in(job_url):
    """
    Obtém o tipo de candidatura de uma vaga do LinkedIn usando um navegador com login.
    Esta função é executada em uma thread separada para não bloquear o processamento principal.
    
    Args:
        job_url (str): URL da vaga no LinkedIn
        
    Returns:
        None (o resultado é colocado na fila application_type_queue)
    """
    try:
        logger.info(f"Iniciando extração do tipo de candidatura com login para: {job_url}")
        
        # Verificar se os pacotes do Selenium estão disponíveis
        selenium_available = True
        try:
            import selenium
            logger.info("Selenium está disponível")
        except ImportError:
            logger.warning("Selenium não está instalado ou não está disponível")
            selenium_available = False
        
        if not selenium_available:
            logger.warning("Selenium não disponível, usando método fallback sem login")
            application_type_queue.put((job_url, "Selenium não disponível"))
            return
        
        try:
            session = get_linkedin_session()
            
            # Tentar fazer login (se ainda não estiver logado)
            if not session.login():
                logger.error("Falha ao fazer login no LinkedIn")
                application_type_queue.put((job_url, "Login Error"))
                return
            
            # Obter detalhes da vaga
            result = session.get_job_details(job_url)
            application_type = result.get("application_type", "Not found")
            
            logger.info(f"Tipo de candidatura obtido com login: {application_type}")
            application_type_queue.put((job_url, application_type))
        except RuntimeError as re:
            logger.error(f"Erro de Selenium/Browser: {str(re)}")
            application_type_queue.put((job_url, "Browser Error"))
        
    except Exception as e:
        logger.error(f"Erro ao obter tipo de candidatura com login: {str(e)}")
        application_type_queue.put((job_url, "Error"))
        
    finally:
        # Não fechar a sessão para reutilizá-la em futuras consultas
        pass

def extract_company_info(url):
    """
    Extract company name, job title, and links from a LinkedIn job listing URL.
    
    Args:
        url (str): LinkedIn job listing URL
        
    Returns:
        dict: Dictionary containing original link, job title, company name, company link, job description, city, announced_at, candidates, and searched_at timestamp
    """
    # Obter data e hora atual para a coluna "searched_at" no formato compatível com Excel
    current_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        # Set headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        # Inicializar o HTMLSession para capturar HTML renderizado
        logger.debug(f"Iniciando HTMLSession para: {url}")
        session = HTMLSession()
        
        # Enviar solicitação e renderizar JavaScript
        try:
            r = session.get(url, headers=headers)
            logger.debug("Página carregada com HTMLSession")
        except Exception as e:
            logger.warning(f"Erro ao carregar com HTMLSession: {str(e)}")
            # Fallback para requests regular
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            r = response
        
        # Usar BeautifulSoup para encontrar elementos fundamentais
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Find company element using the topcard__org-name-link class which is the current structure
        company_element = soup.select_one('a.topcard__org-name-link')
        
        # Find job title element
        job_title_element = soup.select_one('h1.top-card-layout__title')
        
        # MÉTODO 1: HTML renderizado pela sessão - foco no elemento job-details
        job_description_text = ""
        try:
            if hasattr(r, 'html'):
                logger.debug("Extraindo descrição usando HTMLSession e elemento #job-details")
                # Primeiro tentar usando o seletor CSS exato fornecido pelo usuário
                job_details_elements = r.html.find('#job-details')
                if job_details_elements:
                    logger.debug(f"Encontrado elemento #job-details")
                    # Extrair o texto completo do elemento
                    job_description_text = job_details_elements[0].text
                    logger.debug(f"HTMLSession extraiu texto do #job-details com {len(job_description_text)} caracteres")
                else:
                    # Se não encontrar o elemento específico, tentar um seletor alternativo
                    logger.debug("Elemento #job-details não encontrado, tentando outros seletores")
                    job_description_elements = r.html.find('div.description__text, div.show-more-less-html')
                    if job_description_elements:
                        logger.debug(f"Encontrados {len(job_description_elements)} elementos de descrição alternativos")
                        # Extrair o texto completo do elemento
                        job_description_text = job_description_elements[0].text
                        logger.debug(f"HTMLSession extraiu texto alternativo com {len(job_description_text)} caracteres")
        except Exception as e:
            logger.warning(f"Erro ao extrair com HTMLSession: {str(e)}")
        
        # MÉTODO 2: Usar BeautifulSoup para extrair o elemento específico com ID job-details
        if not job_description_text or len(job_description_text) < 100:
            logger.debug("Usando BeautifulSoup para extrair o elemento #job-details")
            job_details_element = soup.select_one('#job-details')
            if job_details_element:
                job_description_text = job_details_element.get_text(separator=' ', strip=True)
                logger.debug(f"BeautifulSoup extraiu {len(job_description_text)} caracteres do #job-details")

        # MÉTODO 3: Usar Trafilatura para extrair todo o conteúdo da página
        if not job_description_text or len(job_description_text) < 100:
            logger.debug("Usando Trafilatura para extrair todo o conteúdo")
            downloaded = trafilatura.fetch_url(url)
            full_text = trafilatura.extract(downloaded, include_comments=False, include_tables=True, 
                                            no_fallback=False, include_links=False, include_formatting=False)
            
            if full_text and len(full_text) > 0:
                logger.debug(f"Trafilatura extraiu {len(full_text)} caracteres")
                # Buscar apenas a parte relevante da descrição do trabalho
                # Geralmente começa após palavras-chave específicas
                job_markers = ["About the job", "Job description", "Responsibilities", 
                               "Qualifications", "Requirements", "About the role", 
                               "Who You Are", "What You Will Do", "Working At"]
                
                start_pos = 0
                for marker in job_markers:
                    pos = full_text.find(marker)
                    if pos > -1:
                        start_pos = pos
                        logger.debug(f"Encontrado marcador '{marker}' na posição {pos}")
                        break
                
                if start_pos > 0:
                    job_description_text = full_text[start_pos:]
                    logger.debug(f"Texto extraído a partir do marcador: {len(job_description_text)} caracteres")
                else:
                    job_description_text = full_text
                    logger.debug(f"Usando texto completo do Trafilatura")
        
        # MÉTODO 4: Usar XPath para extrações específicas
        if not job_description_text or len(job_description_text) < 100:
            try:
                logger.debug("Tentando extrair a descrição usando XPath")
                from lxml import html
                if hasattr(r, 'content'):
                    tree = html.fromstring(r.content)
                elif hasattr(r, 'html') and hasattr(r.html, 'html'):
                    tree = html.fromstring(r.html.html)
                else:
                    logger.warning("Não foi possível obter o conteúdo HTML para análise XPath")
                    raise Exception("Conteúdo HTML não disponível")
                
                # Foco no elemento exato que contém a descrição completa do trabalho
                job_description_elements = []
                xpath_patterns = [
                    # XPath exato fornecido pelo usuário - deve ser o mais preciso
                    '/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[4]/article/div/div[1]//text()',
                    
                    # Seletor CSS alternativo (convertido para XPath)
                    '//*[@id="job-details"]//text()',
                    
                    # Backup: Descrição no formato mais recente (div.show-more-less-html)
                    '//div[contains(@class, "show-more-less-html")]//text()',
                    
                    # Backup: Descrição do trabalho no formato mais recente do LinkedIn
                    '//div[contains(@class, "mt4")]//p[@dir="ltr"]//text()',
                    
                    # Backup: Descrição do trabalho apenas de divs com classe mt4
                    '//div[contains(@class, "mt4")]//text()',
                    
                    # Backup: Descrição do trabalho de parágrafos com direção ltr
                    '//p[@dir="ltr"]//text()'
                ]
                
                # Tentar extrair com cada padrão XPath
                for xpath in xpath_patterns:
                    logger.debug(f"XPath pattern: {xpath}")
                    elements = tree.xpath(xpath)
                    if elements and len(elements) > 0:
                        logger.debug(f"Found {len(elements)} elements with pattern: {xpath}")
                        job_description_elements = elements
                        break
                        
                # Se encontrou elementos, juntar os textos
                if job_description_elements:
                    extracted_text = ' '.join([text.strip() for text in job_description_elements if text.strip()])
                    if len(extracted_text) > len(job_description_text):
                        job_description_text = extracted_text
                        logger.debug(f"XPath extraiu texto maior: {len(job_description_text)} caracteres")
            except Exception as e:
                logger.warning(f"Erro ao extrair com XPath: {str(e)}")
                
        # Fechar a sessão
        try:
            session.close()
        except Exception:
            pass
        if not company_element:
            logger.warning(f"Company element not found for URL: {url}")
            company_name = 'Not found'
            company_link = 'Not found'
        else:
            # Extract company name and link
            company_name = company_element.get_text(strip=True)
            company_link = company_element.get('href', 'Not found')
            
            # Format the company link if it's a relative path
            if company_link != 'Not found' and isinstance(company_link, str) and not company_link.startswith('http'):
                company_link = f"https://www.linkedin.com{company_link}"
        
        # Extract job title
        job_title = 'Not found'
        if job_title_element:
            job_title = job_title_element.get_text(strip=True)
        else:
            logger.warning(f"Job title element not found for URL: {url}")
            
        # Extract job description
        job_description = 'Not found'
        if job_description_text:
            # Limpar a descrição de espaços extras (sem limite de caracteres)
            job_description = ' '.join(job_description_text.split())
            logger.debug(f"Job description extracted successfully. Comprimento total: {len(job_description)} chars. Primeiros 50 chars: {job_description[:50]}...")
        else:
            # Método de último recurso - capturar especificamente os títulos e itens da página
            logger.warning(f"Job description not found for URL: {url}")
            job_description = "Job description not available. Please check the original link."
            
        # Extrair informações adicionais: cidade, data de anúncio, candidatos e tipo de candidatura
        city = 'Not found'
        announced_at = 'Not found'
        candidates = 'Not found'
        
        # Detectar tipo de candidatura usando o método sem login (como fallback)
        application_type = get_application_type_without_login(url, r.text)
        
        # Encontrar o elemento que contém informações sobre cidade, data de anúncio e candidatos
        try:
            # MÉTODO 1: Container específico
            tertiary_container = soup.select_one(".job-details-jobs-unified-top-card__primary-description-container") or \
                                 soup.select_one(".job-details-jobs-unified-top-card__tertiary-description-container")
            
            if tertiary_container:
                logger.debug("Container de informações adicionais encontrado (método 1)")
                
                # Extrair todos os spans com informações de texto
                spans = tertiary_container.select('.tvm__text')
                
                # Processar cada span para identificar o tipo de informação
                for span in spans:
                    span_text = span.get_text(strip=True)
                    
                    # Verificar se o span tem conteúdo
                    if not span_text or span_text in ['.', '·', '']:
                        continue
                    
                    # Identificar o tipo de informação com base no conteúdo
                    if 'candidates' in span_text.lower() or 'applicants' in span_text.lower():
                        candidates = span_text
                        logger.debug(f"Candidatos identificados: {candidates}")
                    elif any(month in span_text.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                        announced_at = span_text
                        logger.debug(f"Data de anúncio identificada: {announced_at}")
                    elif not any(keyword in span_text.lower() for keyword in ['ago', 'hour', 'day', 'week', 'month']):
                        city = span_text
                        logger.debug(f"Cidade identificada: {city}")
            
            # MÉTODO 1 para tipo de candidatura: Busca pelo botão específico ou elemento fornecido - MAIS ABRANGENTE
            # Verificar especificamente por "Easy Apply" e outras variações
            easy_apply_indicators = [
                # Buscar por classes específicas que geralmente indicam Easy Apply
                '.jobs-apply-button--top-card',
                '.jobs-s-apply--fadein',
                '.jobs-s-apply',
                '.artdeco-inline-feedback',
                '.jobs-apply-button',
                '#ember40', # ID específico que pode variar
                'button[data-tracking-control-name="public_jobs_apply-link-offsite_sign-up-now"]',
                'button[data-control-name="jobdetails_topcard_inapply"]',
                '.jobs-s-apply--fadein button',
                '.jobs-apply-button--top-card button'
            ]
            
            # Primeiro, verificar especificamente por "Easy Apply" no texto/classes dos elementos
            for selector in easy_apply_indicators:
                elements = soup.select(selector)
                for element in elements:
                    # Verificar se o elemento ou seus descendentes contêm "Easy Apply"
                    button_text = element.get_text(strip=True)
                    if "easy apply" in button_text.lower() or "candidatura simplificada" in button_text.lower():
                        application_type = "Easy Apply"
                        logger.debug(f"Easy Apply identificado através do seletor {selector}")
                        break
                    
                    # Verificar se o elemento tem a classe ou atributos que indicam Easy Apply
                    class_list = element.get('class', [])
                    if class_list and any("easy" in cls.lower() for cls in class_list):
                        application_type = "Easy Apply"
                        logger.debug(f"Easy Apply identificado através da classe no seletor {selector}")
                        break
                        
                    # Verificar atributos de data ou aria que possam indicar Easy Apply
                    for attr_name, attr_value in element.attrs.items():
                        if isinstance(attr_value, str) and "easy apply" in attr_value.lower():
                            application_type = "Easy Apply"
                            logger.debug(f"Easy Apply identificado através do atributo {attr_name} no seletor {selector}")
                            break
                            
                if application_type != 'Not found':
                    break
                    
            # Se ainda não encontrou, tentar extrair qualquer texto de botão de candidatura
            if application_type == 'Not found':
                apply_button_spans = soup.select('.jobs-apply-button--top-card .artdeco-button__text, .jobs-apply-button span, .jobs-apply-button button span, button.jobs-apply-button span')
                for span in apply_button_spans:
                    button_text = span.get_text(strip=True)
                    if button_text:
                        application_type = button_text
                        logger.debug(f"Tipo de candidatura identificado (método 1): {application_type}")
                        break
            
            # MÉTODO 2: Busca por classes específicas ou padrões comuns
            if city == 'Not found' or announced_at == 'Not found' or candidates == 'Not found' or application_type == 'Not found':
                logger.debug("Tentando método 2 para encontrar informações adicionais")
                
                # Tentar encontrar a localização
                location_elements = soup.select('.job-details-jobs-unified-top-card__bullet, .topcard__flavor--bullet, .job-details-jobs-unified-top-card__workplace-type')
                for element in location_elements:
                    text = element.get_text(strip=True)
                    if text and text not in ['.', '·', ''] and not any(keyword in text.lower() for keyword in ['ago', 'hour', 'day', 'week', 'month', 'remote', 'hybrid']):
                        city = text
                        logger.debug(f"Cidade identificada (método 2): {city}")
                        break
                
                # Tentar encontrar a data de anúncio
                date_elements = soup.select('.job-details-jobs-unified-top-card__subtitle-secondary-grouping .tvm__text, .posted-time-ago__text, .job-details-jobs-unified-top-card__posted-date')
                for element in date_elements:
                    text = element.get_text(strip=True)
                    if text and ('ago' in text.lower() or any(month in text.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])):
                        announced_at = text
                        logger.debug(f"Data de anúncio identificada (método 2): {announced_at}")
                        break
                
                # Tentar encontrar o número de candidatos
                candidate_elements = soup.select('.num-applicants__caption, .jobs-unified-top-card__applicant-count, .job-details-jobs-unified-top-card__applicant-count')
                for element in candidate_elements:
                    text = element.get_text(strip=True)
                    if text and ('applicant' in text.lower() or 'candidate' in text.lower() or 'applied' in text.lower()):
                        candidates = text
                        logger.debug(f"Candidatos identificados (método 2): {candidates}")
                        break
                        
                # Tentar encontrar o tipo de candidatura usando seletores mais genéricos
                if application_type == 'Not found':
                    apply_elements = soup.select('button.jobs-apply-button, button.apply-button, a.apply-button, .jobs-apply-button--top-card button')
                    for element in apply_elements:
                        text = element.get_text(strip=True)
                        if text:
                            application_type = text
                            logger.debug(f"Tipo de candidatura identificado (método 2): {application_type}")
                            break
            
            # MÉTODO 3: Análise de texto para encontrar padrões em todo o documento e XPath
            if city == 'Not found' or announced_at == 'Not found' or candidates == 'Not found' or application_type == 'Not found':
                logger.debug("Tentando método 3 para encontrar informações adicionais")
                
                # Obter todos os textos pequenos da página que poderiam conter informações relevantes
                small_texts = []
                for element in soup.select('span, div.small, p.small, .job-details-jobs-unified-top-card__subtitle-secondary-grouping, button span'):
                    text = element.get_text(strip=True)
                    if len(text) < 100 and len(text) > 2:  # filtrar textos muito curtos ou muito longos
                        small_texts.append(text)
                
                # Procurar padrões para localização
                if city == 'Not found':
                    for text in small_texts:
                        # Verifica se o texto contém algum indicador de cidade/localização
                        if not any(keyword in text.lower() for keyword in ['ago', 'hour', 'day', 'week', 'month', 'remote', 'hybrid', 'applicant', 'candidate']):
                            # Verifica se o texto parece ser uma localização (não contém outros indicadores)
                            if any(char in text for char in [',', '-']) or text.split():
                                city = text
                                logger.debug(f"Cidade identificada (método 3): {city}")
                                break
                
                # Procurar padrões para data de anúncio
                if announced_at == 'Not found':
                    for text in small_texts:
                        if 'ago' in text.lower() or 'posted' in text.lower() or any(month in text.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                            announced_at = text
                            logger.debug(f"Data de anúncio identificada (método 3): {announced_at}")
                            break
                
                # Procurar padrões para número de candidatos
                if candidates == 'Not found':
                    for text in small_texts:
                        if 'applicant' in text.lower() or 'candidate' in text.lower() or 'applied' in text.lower():
                            candidates = text
                            logger.debug(f"Candidatos identificados (método 3): {candidates}")
                            break
                
                # Procurar padrões para tipo de candidatura
                if application_type == 'Not found':
                    application_keywords = ['apply', 'easy apply', 'candidatar', 'candidatura', 'aplicar', 'inscrever']
                    for text in small_texts:
                        if any(keyword in text.lower() for keyword in application_keywords):
                            application_type = text
                            logger.debug(f"Tipo de candidatura identificado (método 3): {application_type}")
                            break
                
                # MÉTODO 4: Tentar usar XPath específico para o tipo de candidatura
                if application_type == 'Not found':
                    try:
                        from lxml import html
                        if hasattr(r, 'content'):
                            tree = html.fromstring(r.content)
                        elif hasattr(r, 'html') and hasattr(r.html, 'html'):
                            tree = html.fromstring(r.html.html)
                        else:
                            logger.warning("Não foi possível obter o conteúdo HTML para análise XPath")
                            raise Exception("Conteúdo HTML não disponível")
                        
                        # Verificar se a URL é .com.br (brasileira) ou internacional
                        is_brazilian = '.com.br' in url or 'br.' in url
                        
                        # Se for versão brasileira, verificar primeiro por "Candidatura simplificada"
                        if is_brazilian:
                            # Procurar por "Candidatura simplificada" em qualquer botão ou elemento
                            simplified_button = tree.xpath('//*[contains(text(), "Candidatura simplificada")]')
                            if simplified_button:
                                application_type = "Easy Apply"
                                logger.debug("Tipo de candidatura identificado como 'Easy Apply' pela versão brasileira (Candidatura simplificada)")
                        
                        # Se ainda não encontrou, verificar na página HTML completa por "Easy Apply"
                        if application_type == 'Not found' and hasattr(r, 'text'):
                            if "candidatura simplificada" in r.text.lower() or "easy apply" in r.text.lower():
                                application_type = "Easy Apply"
                                logger.debug("Tipo de candidatura identificado como 'Easy Apply' pelo texto completo da página")
                        
                        # Se ainda não encontrou, continuar com os padrões XPath
                        xpath_patterns = [
                            # XPath fornecido pelo usuário para versão BR
                            '/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/div/div/div/div[5]/div/div/div/button/span/text()',
                            
                            # XPaths específicos para versão brasileira
                            '//div[contains(@class, "jobs-apply-button")]//button[contains(@aria-label, "Candidatar")]//span/text()',
                            '//button[contains(@data-control-name, "jobdetails_topcard")]//span/text()',
                            
                            # XPaths genéricos
                            '//div[contains(@class, "jobs-apply-button--top-card")]//span[contains(@class, "artdeco-button__text")]/text()',
                            '//button[contains(@class, "jobs-apply-button")]//span/text()',
                            '//button[contains(@class, "apply-button")]//span/text()',
                            '//a[contains(@class, "apply-button")]//span/text()',
                            '//button[contains(@aria-label, "Apply") or contains(@aria-label, "Candidatar")]/span/text()'
                        ]
                        
                        for xpath in xpath_patterns:
                            elements = tree.xpath(xpath)
                            if elements and len(elements) > 0:
                                logger.debug(f"Encontrado tipo de candidatura via XPath: {xpath}")
                                application_type = elements[0].strip()
                                logger.debug(f"Tipo de candidatura identificado (método 4): {application_type}")
                                break
                    except Exception as e:
                        logger.warning(f"Erro ao extrair tipo de candidatura com XPath: {str(e)}")
                
        except Exception as e:
            logger.warning(f"Erro ao extrair informações adicionais: {str(e)}")
        
        logger.debug(f"Extracted job title: {job_title}, company name: {company_name}, company link: {company_link}")
        logger.debug(f"Additional info - city: {city}, announced_at: {announced_at}, candidates: {candidates}")
        
        # Verificar se pode ser uma vaga "Easy Apply" mas não conseguimos detectar devido a limitações de acesso
        # Isso adiciona uma observação para o usuário quando o LinkedIn Brasil retorna "Apply"
        is_brazilian = '.com.br' in url or 'br.' in url or 'mx.linkedin' in url or '.mx' in url or '.lat' in url
        if application_type == 'Apply' and is_brazilian:
            application_type = "Apply (possível Easy Apply*)"
            logger.debug("Adicionado indicador de possível Easy Apply para URL brasileiro/latino")
        
        return {
            'link': url,
            'company_name': company_name,
            'company_link': company_link,
            'job_title': job_title,
            'job_description': job_description,
            'city': city,
            'announced_at': announced_at,
            'candidates': candidates,
            'searched_at': current_datetime,
            'application_type': application_type
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for URL {url}: {str(e)}")
        return {
            'link': url,
            'company_name': f'Error: {str(e)}',
            'company_link': 'Not found',
            'job_title': 'Not found',
            'job_description': 'Not found',
            'city': 'Not found',
            'announced_at': 'Not found',
            'candidates': 'Not found',
            'searched_at': current_datetime,
            'application_type': 'Not found'
        }
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        return {
            'link': url,
            'company_name': f'Error: {str(e)}',
            'company_link': 'Not found',
            'job_title': 'Not found',
            'job_description': 'Not found',
            'city': 'Not found',
            'announced_at': 'Not found',
            'candidates': 'Not found',
            'searched_at': current_datetime,
            'application_type': 'Not found'
        }

def normalize_linkedin_url(url):
    """
    Normaliza um URL do LinkedIn para formato reduzido padrão.
    
    Args:
        url (str): URL completo do LinkedIn
        
    Returns:
        str: URL normalizado no formato https://www.linkedin.com/jobs/view/XXXXXXXXXX
    """
    # Verificar se o URL é válido
    if not url or not isinstance(url, str):
        return url
    
    # Usar regex para extrair o ID de 10 dígitos
    import re
    match = re.search(r'linkedin\.com/jobs/view/(\d{10})', url)
    if match:
        job_id = match.group(1)
        return f"https://www.linkedin.com/jobs/view/{job_id}"
    
    # Tentar outro padrão se o primeiro não funcionar
    match = re.search(r'/jobs/view/([^/?]+)', url)
    if match:
        job_id = match.group(1)
        # Se for numérico e tiver 10 dígitos, usar esse ID
        if job_id.isdigit() and len(job_id) == 10:
            return f"https://www.linkedin.com/jobs/view/{job_id}"
    
    # Se não conseguir extrair o ID, retornar o URL original
    logger.debug(f"Não foi possível normalizar o URL: {url}")
    return url

def calculate_announced_date(searched_at, announced_at):
    """
    Calcula uma data compatível com Excel com base nas informações de Searched At e Announced At.
    
    Args:
        searched_at (str): Data e hora da pesquisa no formato 'YYYY-MM-DD HH:MM:SS'
        announced_at (str): Texto descritivo sobre quando o job foi anunciado, ex. '3 days ago'
        
    Returns:
        str: Data calculada no formato 'YYYY-MM-DD'
    """
    try:
        # Converter searched_at para objeto datetime
        search_date = datetime.datetime.strptime(searched_at, '%Y-%m-%d %H:%M:%S')
        
        if announced_at == 'Not found':
            return 'Not found'
        
        # Padrões para diferentes formatos de announced_at
        patterns = [
            # X days/months/years ago
            (r'(\d+)\s+day', lambda x: datetime.timedelta(days=int(x.group(1)))),
            (r'(\d+)\s+week', lambda x: datetime.timedelta(days=int(x.group(1))*7)),
            (r'(\d+)\s+month', lambda x: datetime.timedelta(days=int(x.group(1))*30)),
            (r'(\d+)\s+year', lambda x: datetime.timedelta(days=int(x.group(1))*365)),
            
            # yesterday, hoje, etc
            (r'yesterday', lambda x: datetime.timedelta(days=1)),
            (r'ontem', lambda x: datetime.timedelta(days=1)),
            (r'today', lambda x: datetime.timedelta(days=0)),
            (r'hoje', lambda x: datetime.timedelta(days=0)),
            
            # horas atrás
            (r'(\d+)\s+hour', lambda x: datetime.timedelta(hours=int(x.group(1)))),
            (r'(\d+)\s+hora', lambda x: datetime.timedelta(hours=int(x.group(1)))),
            
            # minutos atrás
            (r'(\d+)\s+minute', lambda x: datetime.timedelta(minutes=int(x.group(1)))),
            (r'(\d+)\s+minuto', lambda x: datetime.timedelta(minutes=int(x.group(1)))),
        ]
        
        # Verificar se o texto contém algum dos padrões acima
        for pattern, time_delta_func in patterns:
            match = re.search(pattern, announced_at.lower())
            if match:
                delta = time_delta_func(match)
                calculated_date = search_date - delta
                # Retornar no formato YYYY-MM-DD
                return calculated_date.strftime('%Y-%m-%d')
        
        # Verificar se já é uma data específica
        date_patterns = [
            '%b %d, %Y',     # 'Jan 15, 2023'
            '%B %d, %Y',     # 'January 15, 2023'
            '%d %b %Y',      # '15 Jan 2023'
            '%d %B %Y',      # '15 January 2023'
            '%Y-%m-%d',      # '2023-01-15'
            '%d/%m/%Y',      # '15/01/2023'
            '%m/%d/%Y',      # '01/15/2023'
        ]
        
        for pattern in date_patterns:
            try:
                date_object = datetime.datetime.strptime(announced_at, pattern)
                return date_object.strftime('%Y-%m-%d')
            except ValueError:
                pass
        
        # Se nenhum padrão for reconhecido, usar searched_at
        logger.warning(f"Formato de data não reconhecido: {announced_at}. Usando data da pesquisa.")
        return search_date.strftime('%Y-%m-%d')
    
    except Exception as e:
        logger.error(f"Erro ao calcular data anunciada: {str(e)}")
        return 'Error calculating date'

def process_linkedin_urls(urls):
    """
    Process a list of LinkedIn job URLs and return the results as a DataFrame.
    
    Args:
        urls (list): List of LinkedIn job URLs
        
    Returns:
        pandas.DataFrame: DataFrame containing the results
    """
    results = []
    threads = []
    application_type_threads = []
    
    # Processar URLs para extração de informações básicas (sem autenticação)
    for url in urls:
        url = url.strip()
        if url:  # Skip empty URLs
            # Normalizar o URL para o formato reduzido
            normalized_url = normalize_linkedin_url(url)
            logger.debug(f"URL normalizado: {normalized_url}")
            
            # Usar o URL normalizado para extração
            result = extract_company_info(normalized_url)
            
            # Substituir o link original pelo normalizado
            result['link'] = normalized_url
            
            # Calcular a data de anúncio com base nas informações disponíveis
            result['announced_calc'] = calculate_announced_date(
                result['searched_at'], 
                result['announced_at']
            )
            
            results.append(result)
            
            # Verificar se Selenium está disponível antes de iniciar a thread
            selenium_available = True
            try:
                import selenium
                logger.info("Selenium está disponível para detecção precisa")
                
                # Iniciar thread para obter o tipo de candidatura com login
                thread = threading.Thread(target=get_application_type_logged_in, args=(normalized_url,))
                thread.daemon = True  # Thread secundária
                application_type_threads.append(thread)
                thread.start()
            except ImportError:
                logger.warning("Selenium não está disponível, usando apenas o método fallback")
                selenium_available = False
    
    # Verificar se há threads para aguardar
    if application_type_threads:
        # Aguardar um tempo para que algumas threads possam terminar (mas não bloquear por muito tempo)
        logger.info("Aguardando resultados de tipo de candidatura das threads com login...")
        
        # Esperar até 30 segundos para obter os resultados do login
        timeout = time.time() + 30  # 30 segundos de timeout
    else:
        logger.info("Nenhuma thread de Selenium iniciada, usando apenas o método sem login")
        timeout = 0  # Não esperar
    
    # Processar resultados que chegam na fila enquanto esperamos
    while time.time() < timeout:
        try:
            # Verificar se há resultados na fila, sem bloquear
            url, app_type = application_type_queue.get(block=False)
            logger.info(f"Resultado de tipo de candidatura recebido para URL: {url}, tipo: {app_type}")
            
            # Atualizar os resultados com os tipos de candidatura corretos
            for result in results:
                if result['link'] == url and app_type != "Login Error" and app_type != "Not found":
                    logger.info(f"Atualizando tipo de candidatura da URL {url} de '{result['application_type']}' para '{app_type}'")
                    result['application_type'] = app_type
                    break
            
            application_type_queue.task_done()
        except queue.Empty:
            # Sem resultados na fila ainda, esperar um pouco
            time.sleep(0.5)
            
            # Verificar se todas as threads terminaram
            if all(not t.is_alive() for t in application_type_threads):
                logger.info("Todas as threads de tipo de candidatura terminaram")
                break
    
    # Verificar se há mais resultados na fila após o timeout
    try:
        while True:
            url, app_type = application_type_queue.get(block=False)
            logger.info(f"Resultado adicional de tipo de candidatura recebido: {url}, tipo: {app_type}")
            
            # Atualizar resultados
            for result in results:
                if result['link'] == url and app_type != "Login Error" and app_type != "Not found":
                    logger.info(f"Atualizando tipo de candidatura da URL {url} para '{app_type}'")
                    result['application_type'] = app_type
                    break
            
            application_type_queue.task_done()
    except queue.Empty:
        pass
    
    # Adicionar indicador para tipos "Apply" em URLs do LinkedIn Brasil
    for result in results:
        # Verificar se é um URL brasileiro ou latino que ainda mostra "Apply"
        # (apenas se não tivermos conseguido determinar o tipo com login)
        is_brazilian = '.com.br' in result['link'] or 'br.' in result['link'] or 'mx.linkedin' in result['link'] or '.mx' in result['link'] or '.lat' in result['link']
        if is_brazilian and result['application_type'] == 'Apply':
            logger.info(f"Marcando URL brasileira/latina como potencial Easy Apply: {result['link']}")
            result['application_type'] = "Apply (possível Easy Apply*)"
    
    # Create DataFrame from results with columns in the specified order
    df = pd.DataFrame(results, columns=[
        'link', 'company_name', 'company_link', 'job_title', 'job_description', 
        'searched_at', 'announced_at', 'announced_calc', 'city', 'candidates', 'application_type'
    ])
    return df

def get_results_html(urls):
    """
    Process LinkedIn job URLs and return HTML representation of the results.
    
    Args:
        urls (list): List of LinkedIn job URLs
        
    Returns:
        str: HTML representation of the results table
    """
    if not urls:
        return "<p>No URLs provided.</p>"
    
    df = process_linkedin_urls(urls)
    
    # Verificar comprimento das descrições para debug
    for idx, row in df.iterrows():
        logger.debug(f"Linha {idx}: Descrição com {len(row['job_description'])} caracteres")
    
    # Format links as HTML anchor tags before converting to HTML
    df['link'] = df['link'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>' if x != 'Not found' else 'Not found')
    df['company_link'] = df['company_link'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>' if x != 'Not found' else 'Not found')
    
    # Criar tabela HTML personalizada para exibir descrição completa na ordem solicitada
    html_table = """
    <style>
    /* Estilos adicionais aplicados diretamente na tabela */
    .linkedin-job-results-table {
        width: 100%;
        table-layout: fixed;
        border-collapse: collapse;
    }
    
    .linkedin-job-results-table th, 
    .linkedin-job-results-table td {
        white-space: normal;
        word-break: break-word;
        overflow-wrap: break-word;
        text-overflow: clip;
        overflow: visible;
        padding: 10px;
        vertical-align: top;
    }
    
    .linkedin-job-results-table th:nth-child(1), 
    .linkedin-job-results-table td:nth-child(1) {
        width: 10%;
    }
    
    .linkedin-job-results-table th:nth-child(2), 
    .linkedin-job-results-table td:nth-child(2) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(3), 
    .linkedin-job-results-table td:nth-child(3) {
        width: 10%;
    }
    
    .linkedin-job-results-table th:nth-child(4), 
    .linkedin-job-results-table td:nth-child(4) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(5), 
    .linkedin-job-results-table td:nth-child(5) {
        width: 30%;
    }
    
    .linkedin-job-results-table th:nth-child(6), 
    .linkedin-job-results-table td:nth-child(6) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(7), 
    .linkedin-job-results-table td:nth-child(7) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(8), 
    .linkedin-job-results-table td:nth-child(8) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(9), 
    .linkedin-job-results-table td:nth-child(9) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(10), 
    .linkedin-job-results-table td:nth-child(10) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(11), 
    .linkedin-job-results-table td:nth-child(11) {
        width: 8%;
    }
    </style>
    <div class="table-responsive">
      <table class="table table-striped table-hover table-dark linkedin-job-results-table">
        <thead>
          <tr>
            <th>Link</th>
            <th>Company Name</th>
            <th>Company Link</th>
            <th>Job Title</th>
            <th>Job Description</th>
            <th>Searched At</th>
            <th>Announced At</th>
            <th>Announced Calc</th>
            <th>City</th>
            <th>Candidates</th>
            <th>Tipo de Candidatura</th>
          </tr>
        </thead>
        <tbody>
    """
    
    # Adicionar cada linha de forma manual para ter controle total sobre o conteúdo
    for _, row in df.iterrows():
        html_table += f"""
        <tr>
          <td>{row['link']}</td>
          <td>{row['company_name']}</td>
          <td>{row['company_link']}</td>
          <td>{row['job_title']}</td>
          <td class="full-text">{row['job_description']}</td>
          <td>{row['searched_at']}</td>
          <td>{row['announced_at']}</td>
          <td>{row['announced_calc']}</td>
          <td>{row['city']}</td>
          <td>{row['candidates']}</td>
          <td>{row['application_type']}</td>
        </tr>
        """
    
    html_table += """
        </tbody>
      </table>
    </div>
    """
    
    return html_table

def export_to_csv(urls):
    """
    Export LinkedIn job data to CSV format.
    
    Args:
        urls (list): List of LinkedIn job URLs
        
    Returns:
        BytesIO: CSV file as BytesIO object
    """
    if not urls:
        return None
    
    # Get the DataFrame with results
    df = process_linkedin_urls(urls)
    
    # Create a BytesIO object to store the CSV
    csv_buffer = BytesIO()
    
    # Write DataFrame to CSV
    df.to_csv(csv_buffer, index=False, encoding='utf-8')
    
    # Reset buffer position to the beginning
    csv_buffer.seek(0)
    
    return csv_buffer

def export_to_excel(urls):
    """
    Export LinkedIn job data to Excel format.
    
    Args:
        urls (list): List of LinkedIn job URLs
        
    Returns:
        BytesIO: Excel file as BytesIO object
    """
    if not urls:
        return None
    
    # Get the DataFrame with results
    df = process_linkedin_urls(urls)
    
    # Create a BytesIO object to store the Excel file
    excel_buffer = BytesIO()
    
    # Export DataFrame to Excel with specific settings for text handling
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        # Usar o parâmetro 'truncate_sheet' como False para evitar truncamento
        df.to_excel(writer, sheet_name='LinkedIn Jobs', index=False)
        
        # Configurar as opções de célula e worksheet
        worksheet = writer.sheets['LinkedIn Jobs']
        
        # Configurar as colunas
        for i, col in enumerate(df.columns):
            column_letter = chr(65 + i)
            # Obter o comprimento máximo do texto, mas limitado a um valor razoável para a largura
            max_length = min(50, max(df[col].astype(str).apply(len).max(), len(col)) + 2)
            
            # Definir a largura da coluna
            worksheet.column_dimensions[column_letter].width = max_length
            
            # Configurações especiais para a coluna de descrição (coluna E, índice 4)
            if i == 4:  # Job Description column
                # Ajustar altura das linhas automaticamente
                worksheet.column_dimensions[column_letter].width = 100  # Largura máxima
                
                # Configurar células específicas da coluna de descrição
                for row_idx, value in enumerate(df['job_description'], start=2):  # Start from 2 as 1 is header
                    cell = worksheet.cell(row=row_idx, column=i+1)
                    
                    # Definir configurações de célula para textos longos
                    cell.alignment = Alignment(
                        wrap_text=True,
                        vertical='top'
                    )
                    
                    # Configurar altura de linha proporcional ao conteúdo
                    # (Excel ajustará automaticamente com wrap_text=True)
                    
                    # Ajustar a célula para exibir todo o texto
                    # Cada caractere aproximadamente ocupa 0.9 pixel
                    row_height = min(400, max(24, len(str(value)) // 100 * 15))
                    worksheet.row_dimensions[row_idx].height = row_height
    
    # Reset buffer position to the beginning
    excel_buffer.seek(0)
    
    return excel_buffer
