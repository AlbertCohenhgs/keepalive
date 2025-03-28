import os
import time
import requests
import threading
from flask import Flask
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

app = Flask(__name__)

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
            print(f"Requisição bem-sucedida: {response.status_code}")
        else:
            print(f"Requisição não bem-sucedida: {response.status_code}")
        
        return response.status_code
    
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
        return None

def periodic_request(url):
    """Função para realizar requisições periódicas."""
    while True:
        make_request(url)
        time.sleep(120)  # Intervalo de 2 minutos

@app.route('/')
def home():
    """Rota inicial para confirmar que o serviço está rodando."""
    return "Serviço de Keep-Alive está ativo!", 200

def start_background_thread(url):
    """Inicia thread para requisições em segundo plano."""
    thread = threading.Thread(target=periodic_request, args=(url,), daemon=True)
    thread.start()

if __name__ == '__main__':
    target_url = 'https://tokens.sentecamaldita.com.br/'
    
    # Inicia thread de requisições
    start_background_thread(target_url)
    
    # Porta definida para o Render
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)