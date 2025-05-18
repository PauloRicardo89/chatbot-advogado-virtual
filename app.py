from flask import Flask, render_template, request, jsonify, session
import os
import sqlite3
import unicodedata
import re
import requests
import time
import uuid
import datetime
from flask_session import Session

app = Flask(__name__)
# Configuração da sessão Flask
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=31)
Session(app)

# Classe para gerenciar o chatbot
class AdvogadoBot:
    def __init__(self):
        # Inicializar cache para consultas frequentes
        self.cache_consultas = {}
        self.tamanho_max_cache = 100
        
        # Inicializar banco de dados SQLite
        self.inicializar_banco_dados()
        
        # Definição da persona do bot para uso com a API Gemini
        self.prompt_sistema = """
        Você é um assistente jurídico virtual chamado Advogado Virtual. Sua função é fornecer informações gerais sobre leis e procedimentos legais no Brasil.

        Como assistente jurídico, você deve:
        1. Fornecer informações precisas sobre leis brasileiras, códigos e procedimentos legais.
        2. Explicar termos jurídicos em linguagem acessível.
        3. Orientar sobre processos legais comuns (como divórcio, pensão, direitos do consumidor, direito trabalhista, etc.)
        4. Manter um tom profissional, empático e direto.

        Limitações importantes - você DEVE sempre:
        1. Deixar claro que suas informações são apenas orientativas e não substituem um advogado real.
        2. NÃO dar conselhos jurídicos específicos que possam estabelecer uma relação advogado-cliente.
        3. NÃO elaborar petições, contratos ou documentos legais completos.
        4. NÃO prometer resultados em processos.
        5. Recomendar consulta a um advogado para casos específicos.
        6. Ser transparente sobre suas limitações.

        Ao responder, mantenha um tom profissional, informativo, mas acessível. Evite jargões excessivos e explique termos técnicos quando necessário.
        """
        
        print("Chatbot Advogado Virtual inicializado com sucesso!")

    def inicializar_banco_dados(self):
        """Inicializa o banco de dados SQLite para armazenar histórico de conversas"""
        db_path = os.path.join(os.path.dirname(__file__), 'chatbot_data.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Criar tabela de histórico de conversas se não existir
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_conversas (
            id INTEGER PRIMARY KEY,
            id_usuario TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remetente TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            plataforma TEXT DEFAULT 'web'
        )
        ''')
        
        # Criar tabela de usuários se não existir
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario TEXT PRIMARY KEY,
            nome TEXT,
            telefone TEXT,
            email TEXT,
            data_primeiro_contato TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_ultimo_contato TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        self.conn.commit()
    
    def normalizar_texto(self, texto):
        """Normaliza o texto para melhorar correspondência"""
        # Converter para minúsculas
        texto = texto.lower()
        
        # Remover acentos
        texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
        
        # Remover caracteres especiais
        texto = re.sub(r'[^\w\s]', ' ', texto)
        
        # Remover espaços extras
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        return texto
    
    def ler_chave_api(self):
        """Lê a chave da API Gemini de variáveis de ambiente ou arquivo local"""
        try:
            # Buscar no ambiente primeiro (prática recomendada)
            api_key = os.environ.get('GEMINI_API_KEY')
            if api_key:
                return api_key
                
            # Se não encontrou no ambiente, buscar no arquivo local
            caminho_api = os.path.join(os.path.dirname(__file__), 'api-gemini.txt')
            if os.path.exists(caminho_api):
                with open(caminho_api, 'r', encoding='utf-8') as arquivo:
                    chave_api = arquivo.read().strip()
                return chave_api
                
            return None
        except Exception as e:
            print(f"Erro ao ler a chave API: {e}")
            return None
    
    def obter_ou_criar_id_usuario(self):
        """Obtém o ID do usuário da sessão ou cria um novo ID"""
        if 'user_id' not in session:
            session['user_id'] = f"web_{uuid.uuid4()}"
            
            # Registrar novo usuário no banco de dados
            try:
                self.cursor.execute(
                    "INSERT INTO usuarios (id_usuario) VALUES (?)",
                    (session['user_id'],)
                )
                self.conn.commit()
            except Exception as e:
                print(f"Erro ao registrar novo usuário: {e}")
        
        return session['user_id']
    
    def salvar_mensagem(self, id_usuario, remetente, mensagem, plataforma='web'):
        """Salva uma mensagem no histórico de conversas"""
        try:
            self.cursor.execute(
                "INSERT INTO historico_conversas (id_usuario, remetente, mensagem, plataforma) VALUES (?, ?, ?, ?)",
                (id_usuario, remetente, mensagem, plataforma)
            )
            
            # Atualizar data do último contato
            self.cursor.execute(
                "UPDATE usuarios SET data_ultimo_contato = CURRENT_TIMESTAMP WHERE id_usuario = ?",
                (id_usuario,)
            )
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro ao salvar mensagem no histórico: {e}")
            return False
    
    def obter_historico_usuario(self, id_usuario, limite=10):
        """Obtém o histórico recente de conversas do usuário"""
        try:
            self.cursor.execute(
                "SELECT remetente, mensagem FROM historico_conversas WHERE id_usuario = ? ORDER BY timestamp DESC LIMIT ?",
                (id_usuario, limite)
            )
            # Inverter a ordem para ficar cronológico (mais antigo primeiro)
            historico = list(reversed(self.cursor.fetchall()))
            return historico
        except Exception as e:
            print(f"Erro ao obter histórico do usuário: {e}")
            return []
    
    def consultar_gemini(self, pergunta, historico=None, tentativas=3, atraso_inicial=1):
        """Consulta a API Gemini com a pergunta e o histórico da conversa"""
        try:
            chave_api = self.ler_chave_api()
            if not chave_api:
                return False, "Por favor, configure a chave da API Gemini para que eu possa processar suas perguntas adequadamente."

            base_url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent'
            headers = {'Content-Type': 'application/json'}
            params = {'key': chave_api}
            
            # Preparar o contexto da conversa para o Gemini
            contents = []
            
            # Adicionar o prompt de sistema como primeira mensagem
            contents.append({
                "role": "user",  # Gemini usa 'user' para prompt de sistema também
                "parts": [{"text": self.prompt_sistema}]
            })
            
            # Adicionar contexto do histórico (se houver)
            if historico:
                for role, text in historico:
                    gemini_role = "user" if role == "user" else "model"
                    contents.append({
                        "role": gemini_role,
                        "parts": [{"text": text}]
                    })
            
            # Adicionar a pergunta atual
            contents.append({
                "role": "user",
                "parts": [{"text": pergunta}]
            })
            
            # Montar o payload para a API
            data = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 1024,
                }
            }

            atraso = atraso_inicial
            for tentativa in range(1, tentativas + 1):
                try:
                    response = requests.post(base_url, headers=headers, params=params, json=data, timeout=30)
                    
                    if response.status_code == 200:
                        dados = response.json()
                        
                        if 'candidates' in dados and len(dados['candidates']) > 0:
                            resposta = dados['candidates'][0]['content']['parts'][0]['text']
                            resposta = resposta.replace('***', '').replace('**', '')
                            return True, resposta
                        else:
                            return False, "Não consegui formular uma resposta. Poderia reformular sua pergunta?"
                    else:
                        print(f"Erro na requisição: {response.status_code} - {response.text}")
                        
                        # Se for erro de limite de API ou tokens, informar ao usuário
                        if response.status_code in [429, 400]:
                            return False, "Desculpe, estamos com alta demanda no momento. Por favor, tente novamente em alguns instantes."
                        
                        return False, "Houve um erro ao processar sua pergunta."
                        
                except requests.exceptions.ConnectionError:
                    if tentativa < tentativas:
                        time.sleep(atraso)
                        atraso *= 2  # Backoff exponencial
                        continue
                    return False, "Por favor, verifique sua conexão com a internet."
                    
                except requests.exceptions.Timeout:
                    if tentativa < tentativas:
                        time.sleep(atraso)
                        atraso *= 2  # Backoff exponencial
                        continue
                    return False, "A resposta está demorando muito. Por favor, tente novamente mais tarde."

            return False, "Não foi possível obter uma resposta no momento."

        except Exception as e:
            print(f"Ocorreu um erro ao consultar a API: {str(e)}")
            return False, "Ocorreu um erro ao processar sua solicitação."
    
    def obter_resposta(self, pergunta_usuario):
        """Obtém resposta para a pergunta do usuário usando a API Gemini"""
        # Normalizar a pergunta para o cache
        pergunta_normalizada = self.normalizar_texto(pergunta_usuario)
        
        # Verificar cache primeiro para perguntas comuns
        if pergunta_normalizada in self.cache_consultas:
            print("Resposta encontrada no cache!")
            return self.cache_consultas[pergunta_normalizada], False
        
        # Obter ID do usuário da sessão
        id_usuario = self.obter_ou_criar_id_usuario()
        
        # Obter histórico recente da conversa
        historico = self.obter_historico_usuario(id_usuario)
        
        # Consultar API do Gemini com o histórico e a pergunta
        sucesso, resposta = self.consultar_gemini(pergunta_usuario, historico)
        
        # Salvar a interação no histórico
        self.salvar_mensagem(id_usuario, "user", pergunta_usuario)
        if sucesso:
            self.salvar_mensagem(id_usuario, "bot", resposta)
            
            # Guardar no cache se for uma resposta bem sucedida
            # Apenas se o cache não estiver cheio
            if len(self.cache_consultas) < self.tamanho_max_cache:
                self.cache_consultas[pergunta_normalizada] = resposta
                
        return resposta, sucesso


# Inicializar o chatbot
chatbot = AdvogadoBot()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question = data.get('question', '')
    
    if not question:
        return jsonify({'answer': 'Por favor, faça uma pergunta.', 'used_api': False})
    
    # Processar a resposta
    answer, used_api = chatbot.obter_resposta(question)
    
    return jsonify({
        'answer': answer,
        'used_api': used_api
    })

# Endpoint para suporte futuro ao WhatsApp Business API
@app.route('/api/whatsapp/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    # Esta é apenas a estrutura básica para implementação futura
    if request.method == 'GET':
        # Verificação do webhook pelo WhatsApp
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        verify_token = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'token_seguro_para_whatsapp')
        
        if mode == 'subscribe' and token == verify_token:
            return challenge
        return jsonify({'status': 'error', 'message': 'Verificação de webhook falhou'}), 403
    
    elif request.method == 'POST':
        # Aqui seria implementada a lógica para processar mensagens do WhatsApp
        # Implementação futura
        return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    # Obter o endereço IP da máquina para exibir na mensagem
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print(f"Servidor iniciado!")
    print(f"Acesse pelo computador: http://127.0.0.1:5000/")
    print(f"Acesse pelo celular na mesma rede: http://{local_ip}:5000/")
    
    # Permitir conexões externas usando o IP 0.0.0.0 e exibindo o endereço IP da máquina
    app.run(debug=True, host='0.0.0.0')