import requests
from bs4 import BeautifulSoup
import pandas as pd
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_company_info(url):
    """
    Extract company name, job title, job description, and links from a LinkedIn job listing URL.
    
    Args:
        url (str): LinkedIn job listing URL
        
    Returns:
        dict: Dictionary containing original link, job title, company name, company link, and job description
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
        
        # Try different selectors for job description as LinkedIn structure may vary
        job_description_element = soup.select_one('#job-details > div > p')
        
        # If first selector doesn't work, try to get the entire job-details div
        job_details_div = soup.select_one('#job-details')
        
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
        
        # Try the specific paragraph first
        if job_description_element:
            job_description = job_description_element.get_text(strip=True)
        # If that fails, try to get text from the whole job-details div
        elif job_details_div:
            job_description = job_details_div.get_text(strip=True)
            # Clean up extra whitespace
            job_description = ' '.join(job_description.split())
        else:
            logger.warning(f"Job description element not found for URL: {url}")
            
        # Truncate the description if it's too long (for display purposes)
        if job_description != 'Not found' and len(job_description) > 300:
            job_description = job_description[:297] + '...'
        
        logger.debug(f"Extracted job title: {job_title}, company name: {company_name}, job description length: {len(job_description) if job_description != 'Not found' else 0}")
        
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
