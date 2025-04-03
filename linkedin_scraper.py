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

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_company_info(url):
    """
    Extract company name, job title, and links from a LinkedIn job listing URL.
    
    Args:
        url (str): LinkedIn job listing URL
        
    Returns:
        dict: Dictionary containing original link, job title, company name, and company link
    """
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
            logger.debug(f"Job description extracted successfully (first 50 chars): {job_description[:50]}...")
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
            'job_description': job_description
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for URL {url}: {str(e)}")
        return {
            'link': url,
            'company_name': f'Error: {str(e)}',
            'company_link': 'Not found',
            'job_title': 'Not found',
            'job_description': 'Not found'
        }
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        return {
            'link': url,
            'company_name': f'Error: {str(e)}',
            'company_link': 'Not found',
            'job_title': 'Not found',
            'job_description': 'Not found'
        }

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
            result = extract_company_info(url)
            results.append(result)
    
    # Create DataFrame from results with columns in the specified order
    df = pd.DataFrame(results, columns=['link', 'company_name', 'company_link', 'job_title', 'job_description'])
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
    
    # Format links as HTML anchor tags before converting to HTML
    df['link'] = df['link'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>' if x != 'Not found' else 'Not found')
    df['company_link'] = df['company_link'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>' if x != 'Not found' else 'Not found')
    
    # Convert DataFrame to HTML table with Bootstrap styling
    html_table = df.to_html(
        classes='table table-striped table-hover table-dark',
        index=False,
        escape=False
    )
    
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
    
    # Export DataFrame to Excel
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='LinkedIn Jobs', index=False)
        
        # Auto-adjust columns' width
        worksheet = writer.sheets['LinkedIn Jobs']
        for i, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            # Cap width at 50 to avoid overly wide columns
            worksheet.column_dimensions[chr(65 + i)].width = min(max_length, 50)
    
    # Reset buffer position to the beginning
    excel_buffer.seek(0)
    
    return excel_buffer
