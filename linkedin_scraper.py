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
import json
import random
import time
import socket
from requests.exceptions import RequestException, ProxyError, ConnectTimeout

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ProxyManager:
    """
    Gerencia uma lista de proxies gratuitos para rotacionar IPs entre as requisições.
    """
    def __init__(self):
        # Lista de proxies iniciais conhecidos
        self.proxies = []
        self.last_update = None
        self.update_interval = 30 * 60  # 30 minutos em segundos
        # Inicializar a lista de proxies
        self.update_proxy_list()
        
    def update_proxy_list(self):
        """Atualiza a lista de proxies disponíveis de serviços públicos gratuitos"""
        logger.debug("Atualizando lista de proxies")
        
        # Método 1: Usar proxylist.geonode.com
        try:
            url = "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc&filterUpTime=90&protocols=http%2Chttps"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for proxy in data.get('data', []):
                    ip = proxy.get('ip')
                    port = proxy.get('port')
                    protocol = proxy.get('protocols')[0].lower()
                    if ip and port and protocol:
                        proxy_str = f"{protocol}://{ip}:{port}"
                        if proxy_str not in self.proxies:
                            self.proxies.append(proxy_str)
                logger.debug(f"Adicionados {len(data.get('data', []))} proxies do geonode")
        except Exception as e:
            logger.warning(f"Erro ao obter proxies do geonode: {str(e)}")
            
        # Método 2: Usar free-proxy-list.net através de parsing HTML
        try:
            url = "https://free-proxy-list.net/"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.select('table.table tbody tr')
                count = 0
                for row in rows:
                    cols = row.select('td')
                    if len(cols) >= 8:
                        ip = cols[0].text.strip()
                        port = cols[1].text.strip()
                        https = cols[6].text.strip()
                        protocol = 'https' if https == 'yes' else 'http'
                        proxy_str = f"{protocol}://{ip}:{port}"
                        if proxy_str not in self.proxies:
                            self.proxies.append(proxy_str)
                            count += 1
                logger.debug(f"Adicionados {count} proxies do free-proxy-list")
        except Exception as e:
            logger.warning(f"Erro ao obter proxies do free-proxy-list: {str(e)}")
            
        # Método 3: Adicionar alguns proxies conhecidos se a lista estiver vazia
        if not self.proxies:
            logger.warning("Nenhum proxy obtido dos serviços online. Adicionando proxies padrão.")
            default_proxies = [
                "http://34.124.225.130:8080",
                "http://122.9.21.228:8080",
                "http://103.149.146.252:80",
                "http://20.210.113.32:8123",
                "http://20.206.106.192:80",
                "http://165.227.95.162:3128",
                "http://185.162.229.59:80",
                "http://217.249.227.229:8080",
                "http://20.24.43.214:80",
                "http://45.77.198.1:80"
            ]
            self.proxies.extend(default_proxies)
            
        # Filtrar proxies inválidos
        self.proxies = list(set(self.proxies))  # Remover duplicatas
        logger.debug(f"Lista de proxies atualizada. Total: {len(self.proxies)} proxies disponíveis")
        self.last_update = time.time()
        
    def get_random_proxy(self):
        """Retorna um proxy aleatório da lista"""
        # Atualizar a lista de proxies se necessário
        if self.last_update is None or time.time() - self.last_update > self.update_interval or len(self.proxies) < 50:
            self.update_proxy_list()
            
        # Se não houver proxies disponíveis, retorna None
        if not self.proxies:
            logger.warning("Não há proxies disponíveis, tentando fazer requisição direta")
            return None
            
        # Escolher um proxy aleatório
        return random.choice(self.proxies)
    
    def remove_proxy(self, proxy):
        """Remove um proxy inválido da lista"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            logger.debug(f"Proxy {proxy} removido da lista. Restante: {len(self.proxies)} proxies")
            
        # Se houver poucos proxies, atualiza a lista automaticamente
        if len(self.proxies) < 20:
            logger.warning(f"Poucos proxies disponíveis ({len(self.proxies)}), atualizando lista")
            self.update_proxy_list()
    
    def get_session_with_proxy(self, use_html_session=True):
        """Retorna uma sessão com um proxy configurado"""
        # Escolher um proxy aleatório
        proxy = self.get_random_proxy()
        
        if use_html_session:
            session = HTMLSession()
        else:
            session = requests.Session()
            
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
            logger.debug(f"Usando proxy: {proxy}")
        else:
            logger.debug("Usando conexão direta (sem proxy)")
            
        return session, proxy

# Inicializar o gerenciador de proxies
proxy_manager = ProxyManager()

def extract_company_info(url):
    """
    Extract company name, job title, and links from a LinkedIn job listing URL.
    Uses rotating proxies to avoid IP blocking.
    
    Args:
        url (str): LinkedIn job listing URL
        
    Returns:
        dict: Dictionary containing original link, job title, company name, company link, job description, city, announced_at, candidates, and searched_at timestamp
    """
    # Obter data e hora atual para a coluna "searched_at" no formato compatível com Excel
    current_datetime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Headers padrão para simular um navegador
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        # Obter uma sessão com proxy
        logger.debug(f"Iniciando requisição com IP rotativo para: {url}")
        
        # Tentar até 3 proxies diferentes
        for attempt in range(3):
            try:
                # Obter uma sessão HTMLSession com proxy configurado
                session, proxy = proxy_manager.get_session_with_proxy(use_html_session=True)
                
                # Adicionar headers para simular um navegador
                for key, value in headers.items():
                    session.headers[key] = value
                
                # Enviar solicitação e renderizar JavaScript
                r = session.get(url, timeout=30)
                logger.debug(f"Página carregada com sucesso usando {'proxy: ' + proxy if proxy else 'conexão direta'}")
                break  # Se chegou aqui, a requisição foi bem-sucedida
                
            except (ProxyError, ConnectTimeout, RequestException) as e:
                logger.warning(f"Tentativa {attempt+1}/3 falhou: {str(e)}")
                
                # Se o erro foi relacionado ao proxy, removê-lo da lista
                if proxy:
                    proxy_manager.remove_proxy(proxy)
                
                # Se foi a última tentativa, fazer requisição direta
                if attempt == 2:
                    logger.debug("Todas as tentativas com proxy falharam. Tentando conexão direta.")
                    session = HTMLSession()
                    for key, value in headers.items():
                        session.headers[key] = value
                    r = session.get(url, timeout=30)
                    logger.debug("Página carregada com HTMLSession sem proxy")
                    
        # Fallback para requests regular se HTMLSession falhar
        if not r or not hasattr(r, 'html'):
            logger.warning("HTMLSession falhou. Tentando com requests padrão.")
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
            # Preservar quebras de linha originais e formatar para melhor leitura
            # Processar o texto para identificar parágrafos, listas e seções
            
            # 1. Normalizar quebras de linha
            normalized_text = job_description_text.replace('\r\n', '\n').replace('\r', '\n')
            
            # 2. Dividir em parágrafos e itens de lista 
            paragraphs = normalized_text.split('\n\n')
            
            # 3. Processar cada parágrafo/item com formatação apropriada
            formatted_paragraphs = []
            for p in paragraphs:
                # Remover espaços extras dentro de cada parágrafo
                p = ' '.join(p.split())
                
                # Checar se parece um título (primeira letra maiúscula, sem ponto final)
                if p.strip() and p.strip()[0].isupper() and not p.strip().endswith('.') and len(p.strip()) < 100:
                    # Adicionar duas quebras antes de títulos (exceto para o primeiro)
                    if formatted_paragraphs:
                        formatted_paragraphs.append("\n\n" + p.strip())
                    else:
                        formatted_paragraphs.append(p.strip())
                    
                # Checar se é item de lista (começa com * - • ○)
                elif p.strip() and p.strip()[0] in ['•', '*', '-', '○', '◦', '▪', '▫', '→', '»', '►']:
                    formatted_paragraphs.append(p.strip())
                    
                # Parágrafo normal
                else:
                    formatted_paragraphs.append(p.strip())
            
            # 4. Juntar tudo com quebras de linha apropriadas
            job_description = '\n\n'.join(formatted_paragraphs)
            
            # 5. Adicionar quebras no HTML (para exibição na tabela)
            job_description = job_description.replace('\n\n', '<br><br>').replace('\n', '<br>')
            
            logger.debug(f"Job description extracted and formatted successfully. Comprimento total: {len(job_description)} chars. Primeiros 50 chars: {job_description[:50]}...")
        else:
            # Método de último recurso - capturar especificamente os títulos e itens da página
            logger.warning(f"Job description not found for URL: {url}")
            job_description = "Job description not available. Please check the original link."
            
        # Extrair informações adicionais: cidade, data de anúncio e candidatos
        city = 'Not found'
        announced_at = 'Not found'
        candidates = 'Not found'
        
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
            
            # MÉTODO 2: Busca por classes específicas ou padrões comuns
            if city == 'Not found' or announced_at == 'Not found' or candidates == 'Not found':
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
            
            # MÉTODO 3: Análise de texto para encontrar padrões em todo o documento
            if city == 'Not found' or announced_at == 'Not found' or candidates == 'Not found':
                logger.debug("Tentando método 3 para encontrar informações adicionais")
                
                # Obter todos os textos pequenos da página que poderiam conter informações relevantes
                small_texts = []
                for element in soup.select('span, div.small, p.small, .job-details-jobs-unified-top-card__subtitle-secondary-grouping'):
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
                
        except Exception as e:
            logger.warning(f"Erro ao extrair informações adicionais: {str(e)}")
        
        logger.debug(f"Extracted job title: {job_title}, company name: {company_name}, company link: {company_link}")
        logger.debug(f"Additional info - city: {city}, announced_at: {announced_at}, candidates: {candidates}")
        
        return {
            'link': url,
            'company_name': company_name,
            'company_link': company_link,
            'job_title': job_title,
            'job_description': job_description,
            'city': city,
            'announced_at': announced_at,
            'candidates': candidates,
            'searched_at': current_datetime
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
            'searched_at': current_datetime
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
            'searched_at': current_datetime
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

def process_linkedin_urls(urls, progress_callback=None):
    """
    Process a list of LinkedIn job URLs and return the results as a DataFrame.
    Uses IP rotation to avoid blocking and adds random delays between requests.
    
    Args:
        urls (list): List of LinkedIn job URLs
        progress_callback (function, optional): Callback function to update progress
            with signature (current, total, message)
        
    Returns:
        pandas.DataFrame: DataFrame containing the results
    """
    results = []
    
    # Embaralhar URLs para evitar padrões previsíveis de acesso
    random_urls = urls.copy()
    random.shuffle(random_urls)
    
    total_urls = len(random_urls)
    
    # Inicializar progresso
    if progress_callback:
        progress_callback(0, total_urls, "Iniciando extração de dados do LinkedIn...")
    
    for i, url in enumerate(random_urls):
        url = url.strip()
        if url:  # Skip empty URLs
            # Atualizar progresso
            if progress_callback:
                progress_callback(i, total_urls, f"Processando vaga {i+1} de {total_urls}...")
            
            # Adicionar um atraso aleatório entre as requisições para evitar detecção de automação
            if i > 0:
                delay = random.uniform(2.0, 5.0)
                logger.debug(f"Aguardando {delay:.2f} segundos antes da próxima requisição")
                time.sleep(delay)
            
            # Normalizar o URL para o formato reduzido
            normalized_url = normalize_linkedin_url(url)
            logger.debug(f"Processando URL {i+1}/{len(random_urls)}: {normalized_url}")
            
            # Usar o URL normalizado para extração com IP rotativo
            result = extract_company_info(normalized_url)
            
            # Substituir o link original pelo normalizado
            result['link'] = normalized_url
            
            # Calcular a data de anúncio com base nas informações disponíveis
            result['announced_calc'] = calculate_announced_date(
                result['searched_at'], 
                result['announced_at']
            )
            
            results.append(result)
            logger.debug(f"URL {i+1}/{len(random_urls)} processada com sucesso")
            
            # Atualizar progresso após concluir o processamento
            if progress_callback:
                progress_callback(i+1, total_urls, f"Vaga {i+1} de {total_urls} processada")
    
    # Create DataFrame from results with columns in the specified order
    df = pd.DataFrame(results, columns=[
        'link', 'company_name', 'company_link', 'job_title', 'job_description', 
        'searched_at', 'announced_at', 'announced_calc', 'city', 'candidates'
    ])
    
    logger.debug(f"Processamento finalizado. {len(results)} URLs processadas com sucesso.")
    return df

def get_results_html(urls, analyze_jobs=False, progress_callback=None):
    """
    Process LinkedIn job URLs and return HTML representation of the results.
    
    Args:
        urls (list): List of LinkedIn job URLs
        analyze_jobs (bool): Whether to analyze jobs with Gemini AI
        progress_callback (function, optional): Callback function to update progress
            with signature (current, total, message)
        
    Returns:
        str: HTML representation of the results table
        dict: Dictionary containing the processed data for export (if requested)
    """
    if not urls:
        return "<p>No URLs provided.</p>"
    
    # Processar URLs do LinkedIn
    if progress_callback:
        progress_callback(0, 100, "Iniciando extração de dados do LinkedIn...")
    
    # Obter um DataFrame com os dados brutos
    # Nota: analyze_jobs não deve ser passado para process_linkedin_urls, pois é tratado separadamente
    # no get_results_html
    df = process_linkedin_urls(urls, progress_callback=progress_callback)
    
    # Criar uma cópia para exportação antes de modificar com HTML
    df_export = df.copy()
    
    # Verificar comprimento das descrições para debug
    for idx, row in df.iterrows():
        logger.debug(f"Linha {idx}: Descrição com {len(row['job_description'])} caracteres")
    
    # Format links as HTML anchor tags before converting to HTML
    df['link'] = df['link'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>' if x != 'Not found' else 'Not found')
    df['company_link'] = df['company_link'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>' if x != 'Not found' else 'Not found')
    
    # Atualizar progresso após extração do LinkedIn
    if progress_callback:
        progress_callback(len(urls), 100, "Extração de dados do LinkedIn concluída")
    
    # Adicionar colunas para análise Gemini com o novo esquema (inicialmente vazias)
    df['idioma_descricao'] = "N/A"
    df['tipo_vaga'] = "N/A"
    df['industria_vaga'] = "N/A"
    df['foco_vaga'] = "N/A"
    df['fraquezas'] = ""
    df['nota_industria_contexto'] = ""
    df['nota_cargos_anteriores'] = ""
    df['nota_requisitos'] = ""
    df['nota_final'] = ""
    
    # Adicionar as mesmas colunas ao DataFrame de exportação
    df_export['idioma_descricao'] = "N/A"
    df_export['tipo_vaga'] = "N/A"
    df_export['industria_vaga'] = "N/A"
    df_export['foco_vaga'] = "N/A"
    df_export['fraquezas'] = ""
    df_export['nota_industria_contexto'] = ""
    df_export['nota_cargos_anteriores'] = ""
    df_export['nota_requisitos'] = ""
    df_export['nota_final'] = ""
    
    # Analisar vagas com Gemini API se solicitado
    gemini_analyses = []
    job_analyses_html = ""
    
    if analyze_jobs:
        try:
            # Importar o analisador de vagas
            from gemini_analyzer import JobAnalyzer, format_analysis_html
            logger.debug("Importação do analisador Gemini bem-sucedida")
            
            # Atualizar progresso - iniciando análise de vagas
            if progress_callback:
                progress_callback(len(urls), 100 + len(df), "Iniciando análise de compatibilidade com Gemini AI...")
            
            # Preparar os dados para análise
            jobs_for_analysis = []
            url_to_index = {}  # Mapear URLs para seus índices no DataFrame
            
            for i, (idx, row) in enumerate(df.iterrows()):
                # Extrair URL sem tags HTML
                link = row['link']
                if '<a href=' in link:
                    import re
                    url_match = re.search(r'href="([^"]+)"', link)
                    link = url_match.group(1) if url_match else link
                
                job_data = {
                    'job_title': row['job_title'],
                    'company_name': row['company_name'],
                    'job_description': row['job_description'],
                    'link': link,
                    'original_index': idx  # Guardar o índice original
                }
                jobs_for_analysis.append(job_data)
                url_to_index[link] = idx
                
                # Atualizar progresso de preparo para análise
                if progress_callback and i % 2 == 0:
                    progress_callback(
                        len(urls) + i + 1, 
                        100 + len(df) * 2, 
                        f"Preparando análise para vaga {i+1} de {len(df)}..."
                    )
            
            # Inicializar o analisador e processar as vagas
            logger.info(f"Iniciando análise de {len(jobs_for_analysis)} vagas com Gemini API")
            
            # Definir um callback para a análise do Gemini
            gemini_progress_base = len(urls) + len(df)
            gemini_progress_total = len(jobs_for_analysis)
            
            def gemini_progress_callback(current, total, message):
                if progress_callback:
                    progress_callback(
                        gemini_progress_base + current,
                        100 + len(df) * 2 + gemini_progress_total,
                        f"Análise Gemini AI: {message}"
                    )
            
            analyzer = JobAnalyzer()
            analyses_results = analyzer.analyze_jobs_batch(
                jobs_for_analysis,
                progress_callback=gemini_progress_callback
            )
            
            # Armazenar resultados no DataFrame
            for analysis in analyses_results:
                job_link = analysis.get('job_link', '')
                if job_link in url_to_index:
                    idx = url_to_index[job_link]
                    
                    # Obter valores da análise ou usar valores padrão com nova estrutura
                    idioma_descricao = analysis.get('idioma_descricao', 'Não informado')
                    tipo_vaga = analysis.get('tipo_vaga', 'Não informado')
                    industria_vaga = analysis.get('industria_vaga', 'Não informado')
                    foco_vaga = analysis.get('foco_vaga', 'Não informado')
                    fraquezas = analysis.get('fraquezas', '')
                    nota_industria_contexto = analysis.get('nota_industria_contexto', 0)
                    nota_cargos_anteriores = analysis.get('nota_cargos_anteriores', 0)
                    nota_requisitos = analysis.get('nota_requisitos', 0)
                    nota_final = analysis.get('nota_final', 0)
                    
                    # Atualizar o DataFrame de visualização com os resultados da análise
                    df.at[idx, 'idioma_descricao'] = idioma_descricao
                    df.at[idx, 'tipo_vaga'] = tipo_vaga
                    df.at[idx, 'industria_vaga'] = industria_vaga
                    df.at[idx, 'foco_vaga'] = foco_vaga
                    df.at[idx, 'fraquezas'] = fraquezas
                    df.at[idx, 'nota_industria_contexto'] = f"{nota_industria_contexto}%"
                    df.at[idx, 'nota_cargos_anteriores'] = f"{nota_cargos_anteriores}%"
                    df.at[idx, 'nota_requisitos'] = f"{nota_requisitos}%"
                    df.at[idx, 'nota_final'] = f"{nota_final}%"
                    
                    # Atualizar o DataFrame de exportação
                    df_export.at[idx, 'idioma_descricao'] = idioma_descricao
                    df_export.at[idx, 'tipo_vaga'] = tipo_vaga
                    df_export.at[idx, 'industria_vaga'] = industria_vaga
                    df_export.at[idx, 'foco_vaga'] = foco_vaga
                    df_export.at[idx, 'fraquezas'] = fraquezas
                    df_export.at[idx, 'nota_industria_contexto'] = f"{nota_industria_contexto}%"
                    df_export.at[idx, 'nota_cargos_anteriores'] = f"{nota_cargos_anteriores}%"
                    df_export.at[idx, 'nota_requisitos'] = f"{nota_requisitos}%"
                    df_export.at[idx, 'nota_final'] = f"{nota_final}%"
                
                # Salvar para HTML detalhado abaixo da tabela
                gemini_analyses.append(analysis)
            
            # Gerar HTML para cada análise (será exibido abaixo da tabela)
            if progress_callback:
                progress_callback(
                    100 + len(df) * 2 + gemini_progress_total, 
                    100 + len(df) * 2 + gemini_progress_total + 10,
                    "Gerando visualização dos resultados da análise..."
                )
                
            job_analyses_html = "<h2 class='mt-5 mb-4'>Análise Detalhada de Compatibilidade com Gemini AI</h2>"
            for analysis in gemini_analyses:
                job_analyses_html += format_analysis_html(analysis)
            
            logger.info("Análise de vagas concluída com sucesso")
            
            # Finalizar progresso
            if progress_callback:
                progress_callback(
                    100 + len(df) * 2 + gemini_progress_total + 10,
                    100 + len(df) * 2 + gemini_progress_total + 10,
                    "Análise de compatibilidade concluída com sucesso!"
                )
            
        except Exception as e:
            logger.error(f"Erro ao analisar vagas com Gemini API: {str(e)}")
            job_analyses_html = f"""
            <div class="alert alert-danger mt-4">
                <h4>Erro na análise de vagas</h4>
                <p>Não foi possível realizar a análise de compatibilidade: {str(e)}</p>
            </div>
            """
    
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
    
    /* Estilo para colunas de compatibilidade */
    .compatibility-column {
        background-color: rgba(13, 110, 253, 0.1); /* Azul claro semi-transparente */
        font-weight: bold;
    }
    
    /* Estilo para cabeçalhos de compatibilidade */
    .compatibility-header {
        background-color: rgba(13, 110, 253, 0.3); /* Azul mais visível para cabeçalho */
    }
    
    /* Larguras ajustadas para acomodar novas colunas */
    .linkedin-job-results-table th:nth-child(1), 
    .linkedin-job-results-table td:nth-child(1) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(2), 
    .linkedin-job-results-table td:nth-child(2) {
        width: 6%;
    }
    
    .linkedin-job-results-table th:nth-child(3), 
    .linkedin-job-results-table td:nth-child(3) {
        width: 8%;
    }
    
    .linkedin-job-results-table th:nth-child(4), 
    .linkedin-job-results-table td:nth-child(4) {
        width: 7%;
    }
    
    .linkedin-job-results-table th:nth-child(5), 
    .linkedin-job-results-table td:nth-child(5) {
        width: 25%;
    }
    
    .linkedin-job-results-table th:nth-child(6), 
    .linkedin-job-results-table td:nth-child(6) {
        width: 5%;
    }
    
    .linkedin-job-results-table th:nth-child(7), 
    .linkedin-job-results-table td:nth-child(7) {
        width: 5%;
    }
    
    .linkedin-job-results-table th:nth-child(8), 
    .linkedin-job-results-table td:nth-child(8) {
        width: 5%;
    }
    
    .linkedin-job-results-table th:nth-child(9), 
    .linkedin-job-results-table td:nth-child(9) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(10), 
    .linkedin-job-results-table td:nth-child(10) {
        width: 4%;
    }
    
    /* Novas colunas de compatibilidade */
    .linkedin-job-results-table th:nth-child(11), 
    .linkedin-job-results-table td:nth-child(11) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(12), 
    .linkedin-job-results-table td:nth-child(12) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(13), 
    .linkedin-job-results-table td:nth-child(13) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(14), 
    .linkedin-job-results-table td:nth-child(14) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(15), 
    .linkedin-job-results-table td:nth-child(15) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(16), 
    .linkedin-job-results-table td:nth-child(16) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(17), 
    .linkedin-job-results-table td:nth-child(17) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(18), 
    .linkedin-job-results-table td:nth-child(18) {
        width: 4%;
    }
    
    .linkedin-job-results-table th:nth-child(19), 
    .linkedin-job-results-table td:nth-child(19) {
        width: 4%;
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
            <th class="compatibility-header">Idioma</th>
            <th class="compatibility-header">Tipo Vaga</th>
            <th class="compatibility-header">Indústria</th>
            <th class="compatibility-header">Foco</th>
            <th class="compatibility-header">Nota Ind.</th>
            <th class="compatibility-header">Nota Cargos</th>
            <th class="compatibility-header">Nota Req.</th>
            <th class="compatibility-header">Comp. Final</th>
            <th class="compatibility-header">Detalhes</th>
          </tr>
        </thead>
        <tbody>
    """
    
    # Adicionar cada linha de forma manual para ter controle total sobre o conteúdo
    for _, row in df.iterrows():
        # Verificar se temos resultados do Gemini para mostrar (verifica campo novo ou legado)
        has_compatibility = (row.get('compatibilidade_a', '') != "" or 
                            row.get('compatibilidade_b', '') != "" or 
                            row.get('compatibilidade_global', '') != "")
        
        # Criar URL para detalhes da vaga
        job_link = ''
        if 'link' in row and row['link'] and '<a href=' in row['link']:
            import re
            url_match = re.search(r'href="([^"]+)"', row['link'])
            if url_match:
                job_link = url_match.group(1)
                
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
          <td class="compatibility-column">{row.get('idioma_descricao', 'N/A')}</td>
          <td class="compatibility-column">{row.get('tipo_vaga', 'N/A')}</td>
          <td class="compatibility-column">{row.get('industria_vaga', 'N/A')}</td>
          <td class="compatibility-column">{row.get('foco_vaga', 'N/A')}</td>
          <td class="compatibility-column">{row.get('nota_industria_contexto', '')}</td>
          <td class="compatibility-column">{row.get('nota_cargos_anteriores', '')}</td>
          <td class="compatibility-column">{row.get('nota_requisitos', '')}</td>
          <td class="compatibility-column">{row.get('nota_final', '')}</td>
          <td class="compatibility-column">
            <a href="{job_link}" class="btn btn-sm btn-outline-primary" target="_blank">
              Ver
            </a>
          </td>
        </tr>
        """
    
    html_table += """
        </tbody>
      </table>
    </div>
    """
    
    # Adicionar análises de vagas se disponíveis
    html_content = html_table + job_analyses_html
    
    # Retornar o DataFrame de exportação com o conteúdo HTML
    return html_content, df_export

def export_to_csv(urls, df_json=None, analyze_jobs=False):
    """
    Export LinkedIn job data to CSV format.
    
    Args:
        urls (list): List of LinkedIn job URLs
        df_json (str, optional): JSON representation of a previously processed DataFrame
        analyze_jobs (bool): Whether to analyze jobs with Gemini AI if no df_json is provided
        
    Returns:
        BytesIO: CSV file as BytesIO object
    """
    if not urls and not df_json:
        return None
    
    # Se temos um DataFrame em JSON, usar para evitar reprocessamento
    if df_json:
        logger.debug("Usando DataFrame pré-processado do JSON para exportação CSV")
        try:
            import json
            df = pd.read_json(df_json)
        except Exception as e:
            logger.error(f"Erro ao converter JSON para DataFrame: {str(e)}")
            df = None
    
    # Se não temos um DataFrame do JSON, processar novamente
    if df_json is None or df is None:
        logger.debug("Processando URLs novamente para exportação CSV")
        # Processamos primeiro os dados brutos, depois analisamos com Gemini se necessário
        df = process_linkedin_urls(urls, progress_callback=None)
        
        # Se precisamos analisar, precisamos fazer um processamento adicional aqui
        # (Essa lógica deve ser implementada em uma função separada no futuro)
        if analyze_jobs:
            logger.debug("Análise com Gemini solicitada na exportação, mas não implementada diretamente aqui")
            # Idealmente, chamaríamos uma função separada que aplica a análise Gemini ao DataFrame
    
    # Remover colunas com formatação HTML
    if 'link' in df.columns and '<a href=' in str(df['link'].iloc[0]):
        import re
        df['link'] = df['link'].apply(lambda x: re.search(r'href="([^"]+)"', x).group(1) if isinstance(x, str) and '<a href=' in x else x)
    
    if 'company_link' in df.columns and '<a href=' in str(df['company_link'].iloc[0]):
        import re
        df['company_link'] = df['company_link'].apply(lambda x: re.search(r'href="([^"]+)"', x).group(1) if isinstance(x, str) and '<a href=' in x else x)
    
    # Remover formatação HTML da descrição
    df['job_description'] = df['job_description'].apply(lambda x: x.replace('<br><br>', '\n\n').replace('<br>', '\n') if isinstance(x, str) else x)
    
    # Create a BytesIO object to store the CSV
    csv_buffer = BytesIO()
    
    # Write DataFrame to CSV
    df.to_csv(csv_buffer, index=False, encoding='utf-8')
    
    # Reset buffer position to the beginning
    csv_buffer.seek(0)
    
    return csv_buffer

def export_to_excel(urls, df_json=None, analyze_jobs=False):
    """
    Export LinkedIn job data to Excel format.
    
    Args:
        urls (list): List of LinkedIn job URLs
        df_json (str, optional): JSON representation of a previously processed DataFrame
        analyze_jobs (bool): Whether to analyze jobs with Gemini AI if no df_json is provided
        
    Returns:
        BytesIO: Excel file as BytesIO object
    """
    if not urls and not df_json:
        return None
    
    # Se temos um DataFrame em JSON, usar para evitar reprocessamento
    if df_json:
        logger.debug("Usando DataFrame pré-processado do JSON para exportação Excel")
        try:
            import json
            df = pd.read_json(df_json)
        except Exception as e:
            logger.error(f"Erro ao converter JSON para DataFrame: {str(e)}")
            df = None
    
    # Se não temos um DataFrame do JSON, processar novamente
    if df_json is None or df is None:
        logger.debug("Processando URLs novamente para exportação Excel")
        # Processamos primeiro os dados brutos, depois analisamos com Gemini se necessário
        df = process_linkedin_urls(urls, progress_callback=None)
        
        # Se precisamos analisar, precisamos fazer um processamento adicional aqui
        # (Essa lógica deve ser implementada em uma função separada no futuro)
        if analyze_jobs:
            logger.debug("Análise com Gemini solicitada na exportação, mas não implementada diretamente aqui")
            # Idealmente, chamaríamos uma função separada que aplica a análise Gemini ao DataFrame
    
    # Remover colunas com formatação HTML
    if 'link' in df.columns and '<a href=' in str(df['link'].iloc[0]):
        import re
        df['link'] = df['link'].apply(lambda x: re.search(r'href="([^"]+)"', x).group(1) if isinstance(x, str) and '<a href=' in x else x)
    
    if 'company_link' in df.columns and '<a href=' in str(df['company_link'].iloc[0]):
        import re
        df['company_link'] = df['company_link'].apply(lambda x: re.search(r'href="([^"]+)"', x).group(1) if isinstance(x, str) and '<a href=' in x else x)
    
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
                    
                    # Converter os <br> e <br><br> de volta para quebras de linha reais do Excel
                    # para que sejam exibidos corretamente
                    if isinstance(value, str):
                        # Primeiro remover tags HTML
                        clean_value = value.replace('<br><br>', '\n\n').replace('<br>', '\n')
                        # Atribuir valor limpo com quebras de linha reais
                        cell.value = clean_value
                    else:
                        cell.value = value
                    
                    # Definir configurações de célula para textos longos
                    cell.alignment = Alignment(
                        wrap_text=True,
                        vertical='top'
                    )
                    
                    # Contar o número de quebras de linha para ajustar a altura da célula
                    if isinstance(value, str):
                        line_breaks = value.count('<br>') + (value.count('<br><br>') * 2)
                        # Ajustar a altura da linha baseado no conteúdo e número de quebras
                        # Cada linha ocupa aproximadamente 15 unidades de altura
                        base_height = 24  # Altura mínima
                        line_height = 15  # Altura por linha
                        char_per_line = 100  # Caracteres aproximados por linha
                        
                        # Calcular altura com base no comprimento do texto e quebras de linha
                        text_height = (len(clean_value) // char_per_line) * line_height
                        break_height = line_breaks * line_height
                        row_height = min(600, max(base_height, text_height + break_height))
                        
                        # Aplicar altura calculada
                        worksheet.row_dimensions[row_idx].height = row_height
                    else:
                        # Se não for texto, usar altura padrão
                        worksheet.row_dimensions[row_idx].height = 24
    
    # Reset buffer position to the beginning
    excel_buffer.seek(0)
    
    return excel_buffer
