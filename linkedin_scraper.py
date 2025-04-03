import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import trafilatura
import os
import datetime
import csv
from io import BytesIO
from requests_html import HTMLSession
import re
import openpyxl
from openpyxl.styles import Alignment

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_company_info(url):
    """
    Extract company name, job title, and links from a LinkedIn job listing URL.
    
    Args:
        url (str): LinkedIn job listing URL
        
    Returns:
        dict: Dictionary containing original link, job title, company name, company link, job description, searched_at timestamp,
              and additional fields: city, anounced_at, candidates_count, remote, easy
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
                    
                # Extrair os novos campos usando múltiplas abordagens
                city = "Not found"
                anounced_at = "Not found"
                candidates_count = "Not found"
                remote = "Not found"
                easy = "Not found"
                
                try:
                    # ----- Abordagem 1: XPaths originais -----
                    # Cidade - tentar vários padrões
                    city_patterns = [
                        '/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/div/div/div/div[3]/div/span[1]/text()',
                        '//span[contains(@class, "job-details-jobs-unified-top-card__bullet")][1]/text()',
                        '//span[contains(@class, "topcard__flavor")][1]/text()',
                        '//div[contains(@class, "topcard")]//*[contains(@class, "location")]/text()',
                        '//li[contains(@class, "job-criteria__item")][1]//span[contains(@class, "job-criteria__text")]/text()'
                    ]
                    
                    for xpath in city_patterns:
                        city_elements = tree.xpath(xpath)
                        if city_elements and len(city_elements) > 0:
                            city = ' '.join([e.strip() for e in city_elements if e.strip()]).strip()
                            logger.debug(f"Extraído city usando padrão {xpath}: {city}")
                            if city:
                                break
                    
                    # Data de anúncio - tentar vários padrões
                    date_patterns = [
                        '/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/div/div/div/div[3]/div/span[3]/span[2]/text()',
                        '//span[contains(@class, "job-details-jobs-unified-top-card__posted-date")]/text()',
                        '//span[contains(@class, "posted-time-ago__text")]/text()',
                        '//span[contains(@class, "posted-date")]/text()',
                        '//span[contains(text(), "ago")]/text()',
                        '//span[contains(text(), "hour")]/text()',
                        '//span[contains(text(), "day")]/text()',
                        '//span[contains(text(), "month")]/text()',
                        '//span[contains(text(), "week")]/text()'
                    ]
                    
                    for xpath in date_patterns:
                        date_elements = tree.xpath(xpath)
                        if date_elements and len(date_elements) > 0:
                            anounced_at = ' '.join([e.strip() for e in date_elements if e.strip()]).strip()
                            logger.debug(f"Extraído anounced_at usando padrão {xpath}: {anounced_at}")
                            if anounced_at:
                                break
                    
                    # Número de candidatos - tentar vários padrões
                    candidates_patterns = [
                        '/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/div/div/div/div[3]/div/span[5]/text()',
                        '//span[contains(@class, "job-details-jobs-unified-top-card__applicant-count")]/text()',
                        '//span[contains(@class, "num-applicants")]/text()',
                        '//span[contains(text(), "applicant")]/text()',
                        '//span[contains(text(), "candidato")]/text()'
                    ]
                    
                    for xpath in candidates_patterns:
                        candidates_elements = tree.xpath(xpath)
                        if candidates_elements and len(candidates_elements) > 0:
                            candidates_count = ' '.join([e.strip() for e in candidates_elements if e.strip()]).strip()
                            logger.debug(f"Extraído candidates_count usando padrão {xpath}: {candidates_count}")
                            if candidates_count:
                                break
                    
                    # Trabalho remoto - tentar vários padrões
                    remote_patterns = [
                        '/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/div/div/div/div[4]/ul/li[1]/span/span[1]/span/span[1]/text()',
                        '//span[contains(@class, "workplace-type")]/text()',
                        '//span[contains(text(), "Remote")]/text()',
                        '//span[contains(text(), "Remoto")]/text()',
                        '//span[contains(text(), "On-site")]/text()',
                        '//span[contains(text(), "Hybrid")]/text()',
                        '//span[contains(text(), "Híbrido")]/text()',
                        '//li[contains(@class, "job-criteria__item")][2]//span[contains(@class, "job-criteria__text")]/text()'
                    ]
                    
                    for xpath in remote_patterns:
                        remote_elements = tree.xpath(xpath)
                        if remote_elements and len(remote_elements) > 0:
                            remote = ' '.join([e.strip() for e in remote_elements if e.strip()]).strip()
                            logger.debug(f"Extraído remote usando padrão {xpath}: {remote}")
                            if remote:
                                break
                    
                    # Easy Apply - tentar vários padrões
                    easy_patterns = [
                        '/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/div/div/div/div[5]/div/div/div/button/span',
                        '//button[contains(@class, "apply")]/span/text()',
                        '//button[contains(text(), "Apply")]/text()',
                        '//button[contains(text(), "Easy Apply")]/text()',
                        '//button[contains(text(), "Candidatar")]/text()',
                        '//button[contains(@class, "jobs-apply-button")]/span/text()',
                        '//a[contains(@class, "apply")]/span/text()'
                    ]
                    
                    for xpath in easy_patterns:
                        easy_elements = tree.xpath(xpath)
                        if easy_elements and len(easy_elements) > 0:
                            if hasattr(easy_elements[0], 'text_content'):
                                easy = easy_elements[0].text_content().strip()
                            elif isinstance(easy_elements[0], str):
                                easy = easy_elements[0].strip()
                            else:
                                easy = str(easy_elements[0]).strip()
                            
                            logger.debug(f"Extraído easy usando padrão {xpath}: {easy}")
                            if easy:
                                # Verificar se contém "Easy Apply" ou semelhante
                                if "easy" in easy.lower() or "apply" in easy.lower() or "candidatar" in easy.lower():
                                    easy = "Easy Apply"
                                break
                    
                    # ----- Abordagem 2: Busca no HTML completo -----
                    if city == "Not found":
                        # Buscar cidade no texto completo
                        if hasattr(r, 'text'):
                            # Procurar padrões comuns de cidade/localização
                            location_patterns = [
                                r'Location: ([^,\n]+)',
                                r'Localização: ([^,\n]+)',
                                r'Local: ([^,\n]+)',
                                r'Remote in ([^,\n]+)',
                                r'Remoto em ([^,\n]+)',
                                r'Híbrido em ([^,\n]+)',
                                r'Hybrid in ([^,\n]+)'
                            ]
                            
                            for pattern in location_patterns:
                                location_match = re.search(pattern, r.text)
                                if location_match:
                                    city = location_match.group(1).strip()
                                    logger.debug(f"Extraído city do texto usando regex: {city}")
                                    break
                    
                    if anounced_at == "Not found":
                        # Buscar data de publicação no texto completo
                        if hasattr(r, 'text'):
                            # Procurar padrões comuns de datas
                            date_patterns = [
                                r'Posted ([^·\n]+)',
                                r'Publicado há ([^·\n]+)',
                                r'Publicado ([^·\n]+)',
                                r'Posted: ([^·\n]+)',
                                r'Posted about ([^·\n]+)',
                                r'Publicado: ([^·\n]+)'
                            ]
                            
                            for pattern in date_patterns:
                                date_match = re.search(pattern, r.text)
                                if date_match:
                                    anounced_at = date_match.group(1).strip()
                                    logger.debug(f"Extraído anounced_at do texto usando regex: {anounced_at}")
                                    break
                    
                    if candidates_count == "Not found":
                        # Buscar número de candidatos no texto completo
                        if hasattr(r, 'text'):
                            # Procurar padrões comuns de contagem de candidatos
                            candidates_patterns = [
                                r'(\d+)\s+applicant',
                                r'Over (\d+)\s+applicant',
                                r'(\d+)\s+candidato',
                                r'Mais de (\d+)\s+candidato',
                                r'(\d+)\+\s+applicant',
                                r'(\d+)\+\s+candidato'
                            ]
                            
                            for pattern in candidates_patterns:
                                candidates_match = re.search(pattern, r.text)
                                if candidates_match:
                                    candidates_count = f"{candidates_match.group(1).strip()} applicants"
                                    logger.debug(f"Extraído candidates_count do texto usando regex: {candidates_count}")
                                    break
                    
                    if remote == "Not found":
                        # Buscar tipo de trabalho no texto completo
                        if hasattr(r, 'text'):
                            if re.search(r'\bRemote\b', r.text):
                                remote = "Remote"
                            elif re.search(r'\bHybrid\b', r.text):
                                remote = "Hybrid"
                            elif re.search(r'\bOn-site\b', r.text):
                                remote = "On-site"
                            elif re.search(r'\bRemoto\b', r.text):
                                remote = "Remoto"
                            elif re.search(r'\bHíbrido\b', r.text):
                                remote = "Híbrido"
                            elif re.search(r'\bPresencial\b', r.text):
                                remote = "Presencial"
                            
                            if remote != "Not found":
                                logger.debug(f"Extraído remote do texto usando palavras-chave: {remote}")
                    
                    if easy == "Not found":
                        # Verificar se há botão de Easy Apply no texto completo
                        if hasattr(r, 'text'):
                            if re.search(r'Easy Apply', r.text):
                                easy = "Easy Apply"
                            elif re.search(r'Apply now', r.text):
                                easy = "Apply"
                            elif re.search(r'Candidatura Simplificada', r.text):
                                easy = "Easy Apply"
                            elif re.search(r'Candidatar-se já', r.text):
                                easy = "Apply"
                            
                            if easy != "Not found":
                                logger.debug(f"Extraído easy do texto usando palavras-chave: {easy}")
                
                except Exception as e:
                    logger.warning(f"Erro ao extrair campos adicionais com abordagem múltipla: {str(e)}")
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
        
        logger.debug(f"Extracted job title: {job_title}, company name: {company_name}, company link: {company_link}")
        
        return {
            'link': url,
            'company_name': company_name,
            'company_link': company_link,
            'job_title': job_title,
            'job_description': job_description,
            'searched_at': current_datetime,
            'city': city if 'city' in locals() else 'Not found',
            'anounced_at': anounced_at if 'anounced_at' in locals() else 'Not found',
            'candidates_count': candidates_count if 'candidates_count' in locals() else 'Not found',
            'remote': remote if 'remote' in locals() else 'Not found',
            'easy': easy if 'easy' in locals() else 'Not found'
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for URL {url}: {str(e)}")
        return {
            'link': url,
            'company_name': f'Error: {str(e)}',
            'company_link': 'Not found',
            'job_title': 'Not found',
            'job_description': 'Not found',
            'searched_at': current_datetime,
            'city': 'Not found',
            'anounced_at': 'Not found',
            'candidates_count': 'Not found',
            'remote': 'Not found',
            'easy': 'Not found'
        }
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        return {
            'link': url,
            'company_name': f'Error: {str(e)}',
            'company_link': 'Not found',
            'job_title': 'Not found',
            'job_description': 'Not found',
            'searched_at': current_datetime,
            'city': 'Not found',
            'anounced_at': 'Not found',
            'candidates_count': 'Not found',
            'remote': 'Not found',
            'easy': 'Not found'
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

def process_linkedin_urls(urls):
    """
    Process a list of LinkedIn job URLs and return the results as a DataFrame.
    
    Args:
        urls (list): List of LinkedIn job URLs
        
    Returns:
        pandas.DataFrame: DataFrame containing the results
    """
    results = []
    
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
            
            results.append(result)
    
    # Create DataFrame from results with columns in the specified order
    df = pd.DataFrame(results, columns=[
        'link', 'company_name', 'company_link', 'job_title', 'job_description', 'searched_at',
        'city', 'anounced_at', 'candidates_count', 'remote', 'easy'
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
    
    # Criar tabela HTML personalizada para exibir descrição completa
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
        width: 32%;
    }
    
    .linkedin-job-results-table th:nth-child(6), 
    .linkedin-job-results-table td:nth-child(6) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(7), 
    .linkedin-job-results-table td:nth-child(7),
    .linkedin-job-results-table th:nth-child(8), 
    .linkedin-job-results-table td:nth-child(8),
    .linkedin-job-results-table th:nth-child(9), 
    .linkedin-job-results-table td:nth-child(9),
    .linkedin-job-results-table th:nth-child(10), 
    .linkedin-job-results-table td:nth-child(10),
    .linkedin-job-results-table th:nth-child(11), 
    .linkedin-job-results-table td:nth-child(11) {
        width: 6%;
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
            <th>City</th>
            <th>Announced At</th>
            <th>Candidates</th>
            <th>Remote</th>
            <th>Easy Apply</th>
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
          <td>{row['city']}</td>
          <td>{row['anounced_at']}</td>
          <td>{row['candidates_count']}</td>
          <td>{row['remote']}</td>
          <td>{row['easy']}</td>
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
