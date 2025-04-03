import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# Configurar logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('linkedin_login')

# Variáveis de ambiente para credenciais do LinkedIn
LINKEDIN_EMAIL = os.environ.get('LINKEDIN_USERNAME')
LINKEDIN_PASSWORD = os.environ.get('LINKEDIN_PASSWORD')

class LinkedInSession:
    """
    Classe para gerenciar uma sessão do LinkedIn com login.
    """
    
    def __init__(self, headless=True):
        """
        Inicializa a sessão do LinkedIn.
        
        Args:
            headless (bool): Se True, executa o navegador em modo headless (sem interface gráfica)
        """
        self.driver = None
        self.headless = headless
        self.logged_in = False
    
    def start_browser(self):
        """
        Inicia o navegador Chrome com as configurações apropriadas.
        """
        if self.driver:
            logger.info("Browser já está em execução")
            return
        
        try:
            # Verificar se estamos em ambiente Replit
            is_replit = "REPL_ID" in os.environ or "REPLIT_DB_URL" in os.environ
            logger.info(f"Ambiente Replit detectado: {is_replit}")
            
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-dev-shm-usage")
            
            # Adicionar opções para evitar detecção de automação
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            
            # Configurar preferências experimentais
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # Verificar se estamos em ambiente Replit
            if is_replit:
                logger.info("Ajustando configurações para o ambiente Replit")
                try:
                    # Caminho para o Chrome/Chromium no Replit
                    chrome_options.binary_location = '/usr/bin/chromium-browser'
                    # Modo específico para Replit
                    chrome_options.add_argument("--remote-debugging-port=9222")
                    service = Service()
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e:
                    logger.error(f"Erro ao iniciar Chrome no Replit: {str(e)}")
                    raise RuntimeError(f"Não foi possível iniciar o Chrome no Replit: {str(e)}")
            else:
                # Instalar e usar o Chrome via WebDriverManager para ambientes não-Replit
                try:
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e:
                    logger.error(f"Erro ao iniciar Chrome com WebDriverManager: {str(e)}")
                    raise
            
            # Alterar a propriedade navigator.webdriver para evitar detecção
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Navegador iniciado com sucesso")
            
        except WebDriverException as e:
            logger.error(f"Erro ao iniciar o navegador: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao iniciar o navegador: {str(e)}")
            raise RuntimeError(f"Não foi possível iniciar o navegador: {str(e)}")
    
    def login(self):
        """
        Realiza login no LinkedIn usando as credenciais fornecidas.
        
        Returns:
            bool: True se o login for bem-sucedido, False caso contrário
        """
        if not self.driver:
            self.start_browser()
        
        if self.logged_in:
            logger.info("Usuário já está logado no LinkedIn")
            return True
        
        try:
            # Acessar página de login
            self.driver.get('https://www.linkedin.com/login')
            logger.info("Acessando página de login do LinkedIn")
            
            # Esperar pela página carregar
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            # Preencher e-mail
            username_field = self.driver.find_element(By.ID, "username")
            username_field.clear()
            username_field.send_keys(LINKEDIN_EMAIL)
            logger.info(f"Email preenchido: {LINKEDIN_EMAIL[:3]}...{LINKEDIN_EMAIL[-5:]}")
            
            # Preencher senha
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(LINKEDIN_PASSWORD)
            logger.info("Senha preenchida")
            
            # Clicar no botão de login
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
            logger.info("Botão de login clicado")
            
            # Verificar se o login foi bem-sucedido (esperar aparecer a barra de navegação)
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.ID, "global-nav"))
                )
                self.logged_in = True
                logger.info("Login realizado com sucesso")
                return True
            except TimeoutException:
                logger.warning("Falha ao verificar login. Verificando redirecionamento")
                
                # Verificar se foi redirecionado para página de verificação ou página inicial
                current_url = self.driver.current_url
                if "checkpoint" in current_url or "add-phone" in current_url or "challenge" in current_url:
                    logger.error("LinkedIn está solicitando verificação adicional")
                    return False
                elif "feed" in current_url:
                    self.logged_in = True
                    logger.info("Login realizado com sucesso (verificado pela URL)")
                    return True
                else:
                    logger.error(f"URL inesperada após tentativa de login: {current_url}")
                    return False
                
        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}")
            return False
    
    def get_job_details(self, job_url):
        """
        Acessa a página da vaga e extrai informações específicas, incluindo o tipo de candidatura.
        
        Args:
            job_url (str): URL da vaga do LinkedIn
            
        Returns:
            dict: Dicionário com informações da vaga, incluindo o tipo de candidatura
        """
        if not self.logged_in and not self.login():
            logger.error("Não foi possível fazer login. Impossível obter detalhes da vaga.")
            return {"application_type": "Login Error"}
        
        try:
            # Acessar a página da vaga
            self.driver.get(job_url)
            logger.info(f"Acessando página da vaga: {job_url}")
            
            # Esperar para que a página carregue completamente
            time.sleep(3)
            
            # Tentar localizar o botão de candidatura (Easy Apply ou Apply)
            application_type = "Not found"
            
            # Lista de XPaths e seletores CSS para encontrar o botão de candidatura
            selectors = [
                # XPaths para botões de candidatura
                "//button[contains(@class, 'jobs-apply-button')]//span",
                "//button[contains(@data-control-name, 'jobdetails_topcard')]//span",
                "//button[contains(@aria-label, 'Easy Apply')]//span",
                "//button[contains(@aria-label, 'Candidatura simplificada')]//span",
                "//button[contains(@aria-label, 'Apply')]//span",
                "//button[contains(@aria-label, 'Candidatar')]//span",
                
                # CSS Selectors para botões de candidatura
                ".jobs-apply-button--top-card .artdeco-button__text",
                ".jobs-apply-button .artdeco-button__text",
                ".jobs-s-apply button span"
            ]
            
            # Tentar cada seletor
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        # É um XPath
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        # É um CSS Selector
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        for element in elements:
                            button_text = element.text.strip()
                            if button_text:
                                logger.info(f"Tipo de candidatura encontrado: '{button_text}' usando seletor: {selector}")
                                application_type = button_text
                                break
                    
                    if application_type != "Not found":
                        break
                        
                except NoSuchElementException:
                    continue
            
            # Se ainda não encontrou, fazer uma busca mais geral
            if application_type == "Not found":
                logger.info("Tentando capturar qualquer botão de candidatura na página")
                page_source = self.driver.page_source.lower()
                
                if "easy apply" in page_source or "candidatura simplificada" in page_source:
                    logger.info("Encontrado 'Easy Apply' no texto da página")
                    application_type = "Easy Apply"
                elif "apply" in page_source or "candidatar" in page_source:
                    logger.info("Encontrado 'Apply' no texto da página")
                    application_type = "Apply"
            
            return {"application_type": application_type}
            
        except Exception as e:
            logger.error(f"Erro ao obter detalhes da vaga: {str(e)}")
            return {"application_type": f"Error: {str(e)}"}
    
    def close(self):
        """
        Fecha o navegador e encerra a sessão.
        """
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Navegador fechado")
            except Exception as e:
                logger.error(f"Erro ao fechar o navegador: {str(e)}")
            finally:
                self.driver = None
                self.logged_in = False