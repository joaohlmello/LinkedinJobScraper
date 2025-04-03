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
    Extract company name, job title, application type, and links from a LinkedIn job listing URL.
    
    Args:
        url (str): LinkedIn job listing URL
        
    Returns:
        dict: Dictionary containing original link, job title, company name, company link, application type and job description
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
        
        # Inicializar variável para application_type
        application_type = 'Not found'
        
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
                
                # Extrair o tipo de candidatura usando o XPath fornecido
                logger.debug("Tentando extrair o tipo de candidatura usando XPath")
                
                # XPath específico fornecido pelo usuário
                application_type_xpath = '/html/body/div[6]/div[3]/div[2]/div/div/main/div[2]/div[1]/div/div[1]/div/div/div/div[5]/div/div/div/button/span'
                application_type_elements = tree.xpath(application_type_xpath)
                
                if application_type_elements and len(application_type_elements) > 0:
                    application_type = application_type_elements[0].text_content().strip()
                    logger.debug(f"Tipo de candidatura extraído: {application_type}")
                else:
                    # Lista abrangente de XPaths alternativos para o tipo de candidatura
                    # Incluindo variações de estrutura mais comuns do LinkedIn
                    alternative_app_type_xpaths = [
                        # XPaths para botões de candidatura
                        '//button[contains(@class, "jobs-apply-button")]//span/text()',
                        '//button[contains(@class, "jobs-apply-button")]/text()',
                        '//button[contains(@class, "jobs-apply-button")]',
                        '//div[contains(@class, "jobs-apply-button-container")]//button//span/text()',
                        '//div[contains(@class, "apply-button-container")]//button//span/text()',
                        '//div[contains(@class, "jobs-s-apply")]//button//span/text()',
                        
                        # XPaths gerais para botões de aplicação
                        '//button[contains(@aria-label, "Apply") or contains(@aria-label, "Candidatar")]//span/text()',
                        '//button[contains(@data-control-name, "apply")]//span/text()',
                        
                        # XPaths baseados em classes comuns
                        '//span[contains(@class, "jobs-apply-button__text")]/text()',
                        '//span[contains(@class, "artdeco-button__text")]/text()',
                        
                        # XPaths para elementos próximos do botão de aplicação
                        '//*[contains(text(), "Apply") or contains(text(), "Easy Apply") or contains(text(), "Candidatar") or contains(text(), "Candidatura")]/text()',
                        '//div[contains(@class, "jobs-apply-button-container")]//*/text()'
                    ]
                    
                    # Primeiro tentar extrair com text_content para todos os elementos de botão
                    button_elements = tree.xpath('//button[contains(@class, "jobs-apply-button")]')
                    if button_elements and len(button_elements) > 0:
                        application_type = button_elements[0].text_content().strip()
                        if application_type:
                            logger.debug(f"Tipo de candidatura extraído de elemento de botão: {application_type}")
                        
                    # Se não encontrou com método anterior, tentar cada padrão XPath
                    if application_type == 'Not found':
                        for xpath in alternative_app_type_xpaths:
                            app_elements = tree.xpath(xpath)
                            if app_elements and len(app_elements) > 0:
                                # Para elementos de texto, pegar o primeiro valor não vazio
                                for elem in app_elements:
                                    if isinstance(elem, str):
                                        text = elem.strip()
                                    else:
                                        text = elem.text_content().strip() if hasattr(elem, 'text_content') else ""
                                    
                                    if text:
                                        application_type = text
                                        logger.debug(f"Tipo de candidatura extraído de caminho alternativo: {application_type}")
                                        break
                                
                                if application_type != 'Not found':
                                    break
                        
                    # Como último recurso, procurar por termos comuns na página
                    if application_type == 'Not found':
                        common_terms = ["Easy Apply", "Apply", "Apply Now", "Candidatar", "Candidatura Simplificada", 
                                        "Candidatura Externa", "Candidatar Agora", "Candidatar-se", "Apply on company site"]
                        
                        page_text = ' '.join(tree.xpath('//text()'))
                        for term in common_terms:
                            if term in page_text:
                                application_type = term
                                logger.debug(f"Tipo de candidatura extraído de texto da página: {application_type}")
                                break
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
        
        # Log do tipo de candidatura extraído
        logger.debug(f"Tipo de candidatura final: {application_type}")
            
        return {
            'link': url,
            'company_name': company_name,
            'company_link': company_link,
            'job_title': job_title,
            'application_type': application_type,
            'job_description': job_description
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for URL {url}: {str(e)}")
        return {
            'link': url,
            'company_name': f'Error: {str(e)}',
            'company_link': 'Not found',
            'job_title': 'Not found',
            'application_type': 'Not found',
            'job_description': 'Not found'
        }
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        return {
            'link': url,
            'company_name': f'Error: {str(e)}',
            'company_link': 'Not found',
            'job_title': 'Not found',
            'application_type': 'Not found', 
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
    df = pd.DataFrame(results, columns=['link', 'company_name', 'company_link', 'job_title', 'application_type', 'job_description'])
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
        width: 15%;
    }
    
    .linkedin-job-results-table th:nth-child(2), 
    .linkedin-job-results-table td:nth-child(2) {
        width: 10%;
    }
    
    .linkedin-job-results-table th:nth-child(3), 
    .linkedin-job-results-table td:nth-child(3) {
        width: 12%;
    }
    
    .linkedin-job-results-table th:nth-child(4), 
    .linkedin-job-results-table td:nth-child(4) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(5), 
    .linkedin-job-results-table td:nth-child(5) {
        width: 10%;
    }
    
    .linkedin-job-results-table th:nth-child(6), 
    .linkedin-job-results-table td:nth-child(6) {
        width: 45%;
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
            <th>Application Type</th>
            <th>Job Description</th>
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
          <td>{row['application_type']}</td>
          <td class="full-text">{row['job_description']}</td>
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
            
            # Configurações especiais para a coluna de descrição (coluna F, índice 5)
            if i == 5:  # Job Description column
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
