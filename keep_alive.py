import os
import time
import requests
import threading
import logging
import datetime
from flask import Flask, render_template, jsonify
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

app = Flask(__name__)

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Armazenar histórico de requisições para display na UI
request_history = []
MAX_HISTORY_SIZE = 100

def add_to_history(url, status, message_type="info"):
    """Adiciona um evento ao histórico de requisições."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    request_history.append({
        "timestamp": timestamp,
        "url": url,
        "status": status,
        "type": message_type
    })
    
    # Limitar o tamanho do histórico
    if len(request_history) > MAX_HISTORY_SIZE:
        request_history.pop(0)

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
            add_to_history(url, f"Sucesso ({response.status_code})", "success")
        else:
            logger.warning(f"Requisição não bem-sucedida para {url}: {response.status_code}")
            add_to_history(url, f"Falha ({response.status_code})", "error")
        
        return response.status_code
    
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        logger.error(f"Erro na requisição para {url}: {error_msg}")
        add_to_history(url, f"Erro: {error_msg[:50]}...", "error")
        return None

def periodic_request_for_site(url, interval):
    """Função para realizar requisições periódicalhlts para o site Sente Maldita."""
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
    """Rota inicial para exibir a interface do usuário."""
    logger.info("Requisição recebida na rota principal")
    return render_template('index.html')

@app.route('/api/logs')
def get_logs():
    """API para obter logs em tempo real."""
    return jsonify(request_history)

@app.route('/api/status')
def get_status():
    """API para obter status do serviço."""
    status = {
        "status": "online",
        "uptime": get_uptime(),
        "monitored_sites": [
            {"url": "https://tkbeta.onrender.com", "interval": 120},
            {"url": "https://keepalive-yjlx.onrender.com", "interval": 120}
        ]
    }
    return jsonify(status)

def get_uptime():
    """Calcula o tempo de atividade do serviço."""
    delta = datetime.datetime.now() - start_time
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{delta.days} dias, {hours} horas, {minutes} minutos"

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
        args=('https://betastm.onrender.com/login', 20), 
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

# Criar diretório de templates se não existir
if not os.path.exists('templates'):
    os.makedirs('templates')

# Criar template HTML
with open('templates/index.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Keep-Alive Service Monitor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Courier New', monospace;
        }

        body {
            background: #1a1a1a;
            color: #FFD700;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            width: 100%;
        }

        .header {
            text-align: center;
            margin-bottom: 2rem;
        }

        .tokens-title {
            font-size: 2.5rem;
            letter-spacing: 4px;
            text-shadow: 0 0 10px #FFD700;
            margin: 10px 0;
        }

        .status-box, .logs-box {
            background: rgba(0, 0, 0, 0.8);
            border: 2px solid #FFD700;
            padding: 20px;
            margin: 20px 0;
        }

        .status-header, .logs-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            border-bottom: 1px solid #FFD700;
            padding-bottom: 10px;
        }

        .status-title, .logs-title {
            font-size: 1.5rem;
        }

        .status-indicator {
            display: flex;
            align-items: center;
        }

        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-online {
            background-color: #32CD32;
            box-shadow: 0 0 8px #32CD32;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 0.5; }
            50% { opacity: 1; }
            100% { opacity: 0.5; }
        }

        .sites-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .site-card {
            border: 1px solid #FFD700;
            padding: 15px;
            transition: all 0.3s ease;
        }

        .site-card:hover {
            background-color: #FFD700;
            color: #1a1a1a;
            transform: scale(1.02);
        }

        .site-url {
            font-weight: bold;
            margin-bottom: 8px;
            word-break: break-all;
        }

        .site-interval {
            font-size: 0.9rem;
            opacity: 0.8;
        }

        .logs-container {
            height: 300px;
            overflow-y: auto;
            padding: 10px;
            border: 1px solid #4B3800;
            background-color: #000;
        }

        .log-entry {
            margin-bottom: 8px;
            padding: 8px;
            border-left: 3px solid;
            animation: fadeIn 0.3s ease;
        }

        .log-success {
            border-left-color: #32CD32;
        }

        .log-error {
            border-left-color: #FF4500;
            color: #FF4500;
        }

        .log-info {
            border-left-color: #1E90FF;
        }

        .log-timestamp {
            font-size: 0.8rem;
            opacity: 0.7;
            margin-right: 8px;
        }

        .footer {
            text-align: center;
            margin-top: 20px;
            opacity: 0.7;
        }

        .uptime-display {
            text-align: center;
            margin: 15px 0;
            font-size: 1.1rem;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Estilos para dispositivos móveis */
        @media (max-width: 768px) {
            .sites-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="tokens-title">KEEP-ALIVE MONITOR</h1>
        </div>

        <div class="status-box">
            <div class="status-header">
                <h2 class="status-title">Status do Serviço</h2>
                <div class="status-indicator">
                    <div class="status-dot status-online"></div>
                    <span>Online</span>
                </div>
            </div>

            <div class="uptime-display" id="uptime">
                Tempo ativo: Carregando...
            </div>

            <h3>Sites Monitorados:</h3>
            <div class="sites-grid" id="sites-list">
                <!-- Sites serão inseridos via JavaScript -->
            </div>
        </div>

        <div class="logs-box">
            <div class="logs-header">
                <h2 class="logs-title">Logs de Atividade</h2>
                <span id="log-count">0 eventos</span>
            </div>

            <div class="logs-container" id="logs">
                <!-- Logs serão inseridos via JavaScript -->
            </div>
        </div>

        <div class="footer">
            <p>© 2025 - Keep-Alive Service Monitor</p>
        </div>
    </div>

    <script>
        // Função para formatar o timestamp
        function formatTimestamp(timestamp) {
            return timestamp;
        }

        // Função para atualizar os logs
        function updateLogs() {
            fetch('/api/logs')
                .then(response => response.json())
                .then(data => {
                    const logsContainer = document.getElementById('logs');
                    logsContainer.innerHTML = '';
                    
                    // Exibir os logs em ordem reversa (mais recentes primeiro)
                    data.slice().reverse().forEach(log => {
                        const logEntry = document.createElement('div');
                        logEntry.className = `log-entry log-${log.type}`;
                        
                        logEntry.innerHTML = `
                            <span class="log-timestamp">[${formatTimestamp(log.timestamp)}]</span>
                            <span class="log-url">${log.url}</span> - 
                            <span class="log-status">${log.status}</span>
                        `;
                        
                        logsContainer.appendChild(logEntry);
                    });
                    
                    // Atualizar contador de logs
                    document.getElementById('log-count').textContent = `${data.length} eventos`;
                })
                .catch(error => console.error('Erro ao buscar logs:', error));
        }

        // Função para atualizar status
        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // Atualizar uptime
                    document.getElementById('uptime').textContent = `Tempo ativo: ${data.uptime}`;
                    
                    // Atualizar sites monitorados
                    const sitesList = document.getElementById('sites-list');
                    sitesList.innerHTML = '';
                    
                    data.monitored_sites.forEach(site => {
                        const siteCard = document.createElement('div');
                        siteCard.className = 'site-card';
                        
                        siteCard.innerHTML = `
                            <div class="site-url">${site.url}</div>
                            <div class="site-interval">Intervalo: ${site.interval} segundos</div>
                        `;
                        
                        sitesList.appendChild(siteCard);
                    });
                })
                .catch(error => console.error('Erro ao buscar status:', error));
        }

        // Atualizar logs e status inicialmente
        updateLogs();
        updateStatus();
        
        // Configurar atualizações periódicas
        setInterval(updateLogs, 5000);  // Atualizar logs a cada 5 segundos
        setInterval(updateStatus, 30000);  // Atualizar status a cada 30 segundos
    </script>
</body>
</html>
    ''')

if __name__ == '__main__':
    logger.info("Iniciando serviço de Keep-Alive")
    
    # Registrar tempo de início para cálculo de uptime
    start_time = datetime.datetime.now()
    
    start_background_threads()
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Iniciando servidor Flask na porta {port}")
    app.run(host='0.0.0.0', port=port)