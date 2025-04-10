import os
import time
import requests
import threading
import logging
from flask import Flask
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

app = Flask(__name__)

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def configure_retry_strategy():
    """Configuração de estratégia de retry robusta."""
    retry_strategy = Retry(
        total=3,  # Número máximo de tentativas
        status_forcelist=[429, 500, 502, 503, 504],  # Códigos de status para retry
        allowed_methods=["GET"],  # Métodos permitidos para retry
        backoff_factor=1  # Tempo entre as tentativas aumenta exponencialmente
    )
    return retry_strategy

def simulate_browser_headers():
    """Simula headers de um navegador real para evitar bloqueios."""
    return {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

def make_request(url):
    """Realiza requisição com tratamento de erro e retry."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=configure_retry_strategy())
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        response = session.get(
            url, 
            headers=simulate_browser_headers(),
            timeout=10,  # Timeout de 10 segundos
            allow_redirects=True
        )
        
        if response.status_code == 200:
            logger.info(f"Requisição bem-sucedida para {url}: {response.status_code}")
        else:
            logger.warning(f"Requisição não bem-sucedida para {url}: {response.status_code}")
        
        return response.status_code
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição para {url}: {e}")
        return None

def periodic_request_for_site(url, interval):
    """Função para realizar requisições periódicas para o site Sente Maldita."""
    while True:
        logger.info(f"Fazendo requisição para {url}")
        make_request(url)
        logger.info(f"Requisição completa. Aguardando {interval} segundos.")
        time.sleep(interval)

def periodic_request_for_self(url, interval):
    """Função para realizar requisições periódicas para o próprio serviço."""
    while True:
        logger.info(f"Fazendo requisição para o próprio serviço {url}")
        make_request(url)
        logger.info(f"Requisição completa. Aguardando {interval} segundos.")
        time.sleep(interval)

@app.route('/')
def home():
    """Rota inicial para confirmar que o serviço está rodando."""
    logger.info("Requisição recebida na rota principal")
    return "Serviço de Keep-Alive está ativo!", 200

def start_background_threads():
    """Inicia threads para requisições em segundo plano."""
    logger.info("Iniciando thread para o site Sente Maldita a cada 120 segundos")
    site_thread = threading.Thread(
        target=periodic_request_for_site, 
        args=('https://projetokens.sentecamaldita.com.br/', 120), 
        daemon=True
    )
    site_thread.start()
    
    logger.info("Iniciando thread para o site o serviço beta 20s")
    beta_thread = threading.Thread(
        target=periodic_request_for_site, 
        args=('https://betastm.onrender.com/logging', 20), 
        daemon=True
    )
    beta_thread.start()
    
    logger.info("Iniciando thread para o próprio serviço a cada 60 segundos")
    self_thread = threading.Thread(
        target=periodic_request_for_self, 
        args=('https://keepalive-nzb6.onrender.com', 60), 
        daemon=True
    )
    self_thread.start()

if __name__ == '__main__':
    logger.info("Iniciando serviço de Keep-Alive")
    
    # Inicia threads de requisições com diferentes intervalos
    start_background_threads()
    
    # Porta definida para o Render
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Iniciando servidor Flask na porta {port}")
    app.run(host='0.0.0.0', port=port)