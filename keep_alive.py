import os
import time
import requests
import threading
import logging
import datetime
from flask import Flask, render_template, jsonify, request # Adicionado 'request'
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry # Corrigido import para compatibilidade

app = Flask(__name__)

# Configuração do logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- ### NOVO: Armazenamento dinâmico e thread-safe para os sites ### ---
# Lista inicial de sites a serem monitorados
monitored_sites = [
    {"url": "https://tokens.sentecamaldita.com.br", "interval": 120},
    {"url": "https://keepalive-yjlx.onrender.com", "interval": 120}
]
# Lock para garantir que o acesso à lista 'monitored_sites' seja seguro entre threads
sites_lock = threading.Lock()
# --------------------------------------------------------------------------

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
    
    if len(request_history) > MAX_HISTORY_SIZE:
        request_history.pop(0)

def configure_retry_strategy():
    """Configuração de estratégia de retry robusta."""
    return Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        backoff_factor=1
    )

def simulate_browser_headers():
    """Simula headers de um navegador real para evitar bloqueios."""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
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
        response = session.get(url, headers=simulate_browser_headers(), timeout=10, allow_redirects=True)
        
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

# --- ### MODIFICADO: Função genérica para monitoramento ### ---
def periodic_request(url, interval):
    """Função genérica para realizar requisições periódicas para um site."""
    while True:
        logger.info(f"Monitorando {url}")
        make_request(url)
        logger.info(f"Monitoramento de {url} completo. Aguardando {interval} segundos.")
        time.sleep(interval)
# -------------------------------------------------------------

@app.route('/')
def home():
    """Rota inicial para exibir a interface do usuário."""
    logger.info("Requisição recebida na rota principal")
    return render_template('index.html')

@app.route('/api/logs')
def get_logs():
    """API para obter logs em tempo real."""
    return jsonify(request_history)

# --- ### MODIFICADO: Rota de status para ler a lista dinâmica ### ---
@app.route('/api/status')
def get_status():
    """API para obter status do serviço."""
    with sites_lock:
        # Copia a lista para evitar problemas de concorrência durante a serialização do JSON
        current_sites = list(monitored_sites)
    
    status = {
        "status": "online",
        "uptime": get_uptime(),
        "monitored_sites": current_sites
    }
    return jsonify(status)
# -------------------------------------------------------------------

# --- ### NOVO: Endpoint para adicionar um novo site ### ---
@app.route('/api/add_site', methods=['POST'])
def add_site():
    """API para adicionar um novo site para monitoramento."""
    data = request.get_json()
    if not data or 'url' not in data or 'interval' not in data:
        return jsonify({"status": "error", "message": "Dados inválidos."}), 400

    new_url = data['url']
    try:
        new_interval = int(data['interval'])
        if new_interval < 30: # Impõe um limite mínimo para evitar abuso
            return jsonify({"status": "error", "message": "O intervalo deve ser de no mínimo 30 segundos."}), 400
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "O intervalo deve ser um número inteiro."}), 400

    with sites_lock:
        # Verifica se o site já está sendo monitorado
        if any(site['url'] == new_url for site in monitored_sites):
            return jsonify({"status": "error", "message": "Este site já está sendo monitorado."}), 409
        
        # Adiciona o novo site à lista
        new_site = {"url": new_url, "interval": new_interval}
        monitored_sites.append(new_site)
        logger.info(f"Novo site adicionado para monitoramento: {new_url} a cada {new_interval}s")

        # Inicia uma nova thread de monitoramento para o novo site
        thread = threading.Thread(target=periodic_request, args=(new_url, new_interval), daemon=True)
        thread.start()

    return jsonify({"status": "success", "message": f"Site {new_url} adicionado com sucesso."})
# -----------------------------------------------------------

def get_uptime():
    delta = datetime.datetime.now() - start_time
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{delta.days} dias, {hours} horas, {minutes} minutos"

# --- ### MODIFICADO: Função para iniciar threads dinamicamente ### ---
def start_background_threads():
    """Inicia threads para requisições em segundo plano para todos os sites configurados."""
    logger.info("Iniciando threads de monitoramento em segundo plano...")
    with sites_lock:
        for site in monitored_sites:
            url = site["url"]
            interval = site["interval"]
            logger.info(f"Iniciando thread para {url} a cada {interval} segundos")
            thread = threading.Thread(
                target=periodic_request, 
                args=(url, interval), 
                daemon=True
            )
            thread.start()
# -------------------------------------------------------------------

# Criar diretório de templates se não existir
if not os.path.exists('templates'):
    os.makedirs('templates')

# --- ### MODIFICADO: Template HTML com formulário de adição ### ---
with open('templates/index.html', 'w', encoding='utf-8') as f:
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
        .header { text-align: center; margin-bottom: 2rem; }
        .tokens-title { font-size: 2.5rem; letter-spacing: 4px; text-shadow: 0 0 10px #FFD700; margin: 10px 0; }
        .box {
            background: rgba(0, 0, 0, 0.8);
            border: 2px solid #FFD700;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
        }
        .box-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px solid #FFD700; padding-bottom: 10px; }
        .box-title { font-size: 1.5rem; }
        .status-indicator { display: flex; align-items: center; }
        .status-dot { width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }
        .status-online { background-color: #32CD32; box-shadow: 0 0 8px #32CD32; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { opacity: 0.5; } 50% { opacity: 1; } 100% { opacity: 0.5; } }
        .sites-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
        .site-card { border: 1px solid #FFD700; padding: 15px; transition: all 0.3s ease; border-radius: 4px; }
        .site-card:hover { background-color: rgba(255, 215, 0, 0.1); transform: scale(1.02); }
        .site-url { font-weight: bold; margin-bottom: 8px; word-break: break-all; }
        .site-interval { font-size: 0.9rem; opacity: 0.8; }
        .logs-container { height: 300px; overflow-y: auto; padding: 10px; border: 1px solid #4B3800; background-color: #000; border-radius: 4px; }
        .log-entry { margin-bottom: 8px; padding: 8px; border-left: 3px solid; animation: fadeIn 0.3s ease; }
        .log-success { border-left-color: #32CD32; }
        .log-error { border-left-color: #FF4500; color: #FF4500; }
        .log-info { border-left-color: #1E90FF; }
        .log-timestamp { font-size: 0.8rem; opacity: 0.7; margin-right: 8px; }
        .footer { text-align: center; margin-top: 20px; opacity: 0.7; }
        .uptime-display { text-align: center; margin: 15px 0; font-size: 1.1rem; }
        .form-grid { display: grid; grid-template-columns: 1fr auto; gap: 10px; margin-top: 15px; }
        .form-grid input { background: #333; border: 1px solid #FFD700; color: #FFD700; padding: 10px; width: 100%; border-radius: 4px; }
        .form-grid input::placeholder { color: #aaa; }
        .form-grid button { background: #FFD700; color: #1a1a1a; border: none; padding: 10px 20px; cursor: pointer; font-weight: bold; transition: background-color 0.3s; border-radius: 4px; }
        .form-grid button:hover { background: #ffd800a6; }
        #form-message { margin-top: 10px; text-align: center; font-size: 0.9rem; height: 1em; }
        .message-success { color: #32CD32; }
        .message-error { color: #FF4500; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
        @media (max-width: 768px) { .form-grid { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1 class="tokens-title">KEEP-ALIVE MONITOR</h1>
        </header>

        <section class="box">
            <div class="box-header">
                <h2 class="box-title">Status do Serviço</h2>
                <div class="status-indicator">
                    <div class="status-dot status-online"></div>
                    <span>Online</span>
                </div>
            </div>
            <div class="uptime-display" id="uptime">Tempo ativo: Carregando...</div>
            <h3>Sites Monitorados:</h3>
            <div class="sites-grid" id="sites-list"></div>
        </section>
        
        <section class="box">
            <div class="box-header">
                <h2 class="box-title">Adicionar Novo Site</h2>
            </div>
            <form id="add-site-form">
                <div class="form-grid">
                    <input type="url" id="site-url" placeholder="https://exemplo.com" required>
                    <input type="number" id="site-interval" placeholder="Intervalo (segundos, min. 30)" min="30" required>
                    <button type="submit">Adicionar</button>
                </div>
                 <div id="form-message"></div>
            </form>
        </section>

        <section class="box">
            <div class="box-header">
                <h2 class="box-title">Logs de Atividade</h2>
                <span id="log-count">0 eventos</span>
            </div>
            <div class="logs-container" id="logs"></div>
        </section>

        <footer class="footer">
            <p>© 2025 - Keep-Alive Service Monitor</p>
        </footer>
    </div>

    <script>
        const API_URLS = {
            logs: '/api/logs',
            status: '/api/status',
            addSite: '/api/add_site'
        };

        function updateLogs() {
            fetch(API_URLS.logs)
                .then(response => response.json())
                .then(data => {
                    const logsContainer = document.getElementById('logs');
                    logsContainer.innerHTML = '';
                    data.slice().reverse().forEach(log => {
                        const logEntry = document.createElement('div');
                        logEntry.className = `log-entry log-${log.type}`;
                        logEntry.innerHTML = `
                            <span class="log-timestamp">[${log.timestamp}]</span>
                            <span class="log-url">${log.url}</span> - 
                            <span class="log-status">${log.status}</span>
                        `;
                        logsContainer.appendChild(logEntry);
                    });
                    document.getElementById('log-count').textContent = `${data.length} eventos`;
                })
                .catch(error => console.error('Erro ao buscar logs:', error));
        }

        function updateStatus() {
            fetch(API_URLS.status)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('uptime').textContent = `Tempo ativo: ${data.uptime}`;
                    const sitesList = document.getElementById('sites-list');
                    sitesList.innerHTML = '';
                    if (data.monitored_sites.length === 0) {
                        sitesList.innerHTML = '<p>Nenhum site sendo monitorado.</p>';
                        return;
                    }
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
        
        // Função para lidar com a submissão do formulário
        document.getElementById('add-site-form').addEventListener('submit', function(event) {
            event.preventDefault();
            const url = document.getElementById('site-url').value;
            const interval = document.getElementById('site-interval').value;
            const messageEl = document.getElementById('form-message');

            fetch(API_URLS.addSite, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, interval: parseInt(interval, 10) })
            })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                messageEl.textContent = data.message;
                if (ok) {
                    messageEl.className = 'message-success';
                    document.getElementById('add-site-form').reset();
                    updateStatus(); // Atualiza a lista de sites imediatamente
                } else {
                    messageEl.className = 'message-error';
                }
            })
            .catch(error => {
                console.error('Erro ao adicionar site:', error);
                messageEl.textContent = 'Erro de conexão ao tentar adicionar o site.';
                messageEl.className = 'message-error';
            });
            
            // Limpa a mensagem após alguns segundos
            setTimeout(() => { messageEl.textContent = ''; }, 5000);
        });

        // Inicialização e atualizações periódicas
        updateLogs();
        updateStatus();
        setInterval(updateLogs, 5000);
        setInterval(updateStatus, 30000);
    </script>
</body>
</html>
    ''')
# --------------------------------------------------------------------

if __name__ == '__main__':
    logger.info("Iniciando serviço de Keep-Alive")
  
    start_time = datetime.datetime.now()
    
    # Inicia as threads para os sites que já estão na lista inicial
    start_background_threads()
    
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Iniciando servidor Flask na porta {port}")
    app.run(host='0.0.0.0', port=port)
