import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import trafilatura
import os
import datetime
import csv
from io import BytesIO

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
        
        # Send GET request to the URL
        logger.debug(f"Sending request to: {url}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find company element using the topcard__org-name-link class which is the current structure
        company_element = soup.select_one('a.topcard__org-name-link')
        
        # Find job title element
        job_title_element = soup.select_one('h1.top-card-layout__title')
        
        # Usar Trafilatura para extrair o conteúdo textual completo da página
        logger.debug("Usando Trafilatura para extrair a descrição do trabalho")
        downloaded = trafilatura.fetch_url(url)
        full_text = trafilatura.extract(downloaded)
        
        # Tenta extrair a descrição completa do trabalho do texto
        job_description_text = ""
        if full_text:
            # Usar o texto completo como descrição do trabalho
            job_description_text = full_text
            
            # Melhorar a extração removendo partes irrelevantes
            # Dividir o texto em linhas para análise
            lines = full_text.split('\n')
            
            # Procurar por palavras-chave que indicam o início da descrição do trabalho
            job_description_section = []
            found_description = False
            
            for i, line in enumerate(lines):
                # Lista expandida de palavras-chave que podem indicar a seção de descrição do trabalho
                keywords = [
                    'sobre o cargo', 'descrição', 'job description', 'about the job', 
                    'sobre a vaga', 'responsabilidades', 'responsibilities', 
                    'requisitos', 'requirements', 'qualificações', 'qualifications',
                    'atividades', 'activities', 'atribuições', 'duties', 
                    'o que você vai fazer', 'what you will do'
                ]
                
                # Verificar se a linha contém alguma das palavras-chave
                if any(keyword in line.lower() for keyword in keywords):
                    found_description = True
                
                # Se encontramos a seção de descrição, vamos coletá-la
                if found_description:
                    job_description_section.append(line)
            
            # Se encontramos alguma seção específica, use-a
            if job_description_section:
                job_description_text = '\n'.join(job_description_section)
                
        # Usar lxml como backup se o Trafilatura não funcionar bem
        if not job_description_text:
            logger.debug("Trafilatura não encontrou descrição, usando lxml como backup")
            from lxml import html
            tree = html.fromstring(response.content)
            
            # Tenta vários XPaths para encontrar a descrição
            job_description_elements = []
            
            # Lista expandida de XPath para capturar a descrição do trabalho
            xpath_patterns = [
                # XPath para seção de job-details, que geralmente contém a descrição
                '//*[@id="job-details"]//text()',
                
                # XPaths para formatos comuns no LinkedIn
                '//div[contains(@class, "description")]//text()', 
                '//section[contains(@class, "description")]//text()',
                '//div[contains(@class, "show-more-less-html")]//text()',
                
                # XPaths mais específicos para conteúdo de descrição de trabalho
                '//div[contains(@class, "job-description")]//text()',
                '//div[@id="job-details"]//text()',
                '//div[contains(@class, "jobs-description")]//text()',
                '//div[contains(@class, "jobs-box__html-content")]//text()',
                '//div[contains(@class, "jobs-box__details")]//text()',
                
                # XPath mais genérico para pegar todo o conteúdo
                '//main//text()'
            ]
            
            # Tentar cada padrão até encontrar um que retorne conteúdo
            for xpath in xpath_patterns:
                elements = tree.xpath(xpath)
                if elements:
                    job_description_elements.extend(elements)
                    # Se já encontramos conteúdo suficiente, podemos parar
                    if len(job_description_elements) > 20:  # Suficiente para uma descrição razoável
                        break
                
            # Se encontrou elementos com lxml, junta-os
            if job_description_elements:
                job_description_text = ' '.join([text.strip() for text in job_description_elements if text.strip()])
        
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
            # Tentar usar elementos capturados pelo método de backup (lxml)
            job_description_elements = []
            try:
                # Tentar extrair novamente a descrição usando lxml se necessário
                from lxml import html
                tree = html.fromstring(response.content)
                
                # Usar os mesmos padrões XPath que definimos anteriormente
                job_description_elements = []
                
                # Lista de padrões XPath a serem testados
                xpath_patterns = [
                    '//*[@id="job-details"]//text()',
                    '//div[contains(@class, "description")]//text()', 
                    '//section[contains(@class, "description")]//text()',
                    '//div[contains(@class, "show-more-less-html")]//text()',
                    '//div[contains(@class, "job-description")]//text()',
                    '//div[@id="job-details"]//text()',
                    '//div[contains(@class, "jobs-description")]//text()',
                    '//div[contains(@class, "jobs-box__html-content")]//text()',
                    '//div[contains(@class, "jobs-box__details")]//text()',
                    '//main//text()'
                ]
                
                # Testar cada padrão
                for xpath in xpath_patterns:
                    elements = tree.xpath(xpath)
                    if elements:
                        job_description_elements.extend(elements)
                        if len(job_description_elements) > 20:
                            break
                
                if job_description_elements:
                    job_description = ' '.join([text.strip() for text in job_description_elements if text.strip()])
                else:
                    logger.warning(f"Job description not found for URL: {url}")
            except Exception as e:
                logger.warning(f"Failed to extract job description using backup method: {str(e)}")
        
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
