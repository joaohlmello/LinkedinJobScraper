import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging
import trafilatura

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
        
        # Tenta extrair a parte relevante da descrição do trabalho do texto completo
        job_description_text = ""
        if full_text:
            # Dividir o texto em linhas para procurar a descrição do trabalho
            lines = full_text.split('\n')
            
            # Encontrar índices de possíveis seções de descrição
            for i, line in enumerate(lines):
                if any(keyword in line.lower() for keyword in ['sobre o cargo', 'descrição', 'job description', 'about the job']):
                    # Pegar as próximas 10 linhas como parte da descrição (ou até o fim do texto)
                    end_idx = min(i + 10, len(lines))
                    job_description_text = '\n'.join(lines[i:end_idx])
                    break
            
            # Se não encontrou nenhuma seção específica, use o texto completo
            if not job_description_text and full_text:
                job_description_text = full_text
                
        # Usar lxml como backup se o Trafilatura não funcionar bem
        if not job_description_text:
            logger.debug("Trafilatura não encontrou descrição, usando lxml como backup")
            from lxml import html
            tree = html.fromstring(response.content)
            
            # Tenta vários XPaths para encontrar a descrição
            job_description_elements = []
            
            # XPath para seção de job-details, que geralmente contém a descrição
            job_details = tree.xpath('//*[@id="job-details"]//text()')
            if job_details:
                job_description_elements.extend(job_details)
                
            # Se não encontrou nada, tenta outros seletores comuns
            if not job_description_elements:
                job_description_elements = tree.xpath('//div[contains(@class, "description")]//text() | //section[contains(@class, "description")]//text()')
                
            # Se ainda não encontrou, tenta uma abordagem mais genérica
            if not job_description_elements:
                job_description_elements = tree.xpath('//div[contains(@class, "show-more-less-html")]//text()')
                
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
            # Limpar a descrição de espaços extras e limitar a 500 caracteres
            job_description = ' '.join(job_description_text.split())
            if len(job_description) > 500:
                job_description = job_description[:497] + '...'
            logger.debug(f"Job description extracted successfully (first 50 chars): {job_description[:50]}...")
        else:
            # Tentar usar elementos capturados pelo método de backup (lxml)
            job_description_elements = []
            try:
                # Tentar extrair novamente a descrição usando lxml se necessário
                from lxml import html
                tree = html.fromstring(response.content)
                job_description_elements = tree.xpath('//*[@id="job-details"]//text()')
                
                if job_description_elements:
                    job_description = ' '.join([text.strip() for text in job_description_elements if text.strip()])
                    if len(job_description) > 500:
                        job_description = job_description[:497] + '...'
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
