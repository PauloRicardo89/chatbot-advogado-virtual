from flask import Flask, render_template, request, jsonify, session
import os
import sqlite3
import unicodedata
import re
import requests
import time
import uuid
import datetime
import json
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlencode
from flask_session import Session
import random

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
        
        # Inicializar banco de dados SQLite apenas para histórico
        self.inicializar_banco_dados()
        
        # Definição da persona do bot para uso com a API Gemini - Versão aprimorada
        self.prompt_sistema = """
        Você é um assistente jurídico virtual chamado Advogado Virtual. Sua função é fornecer informações gerais sobre leis e procedimentos legais no Brasil.
        Você foi Criado por Paulo Ricardo, estudante de analise e desenvolvimento de sistemas pela univercidade Unicarioca, no intuito de ser um colaborador aos estudos da esposa do mesmo chamada de Esther rodrigues, que estudo direito na mesma univecidade.
        Você deve agir como um advogado virtual, fornecendo informações úteis e precisas sobre questões jurídicas comuns, como direito civil, direito do consumidor, direito trabalhista, entre outros.
        
        Como assistente jurídico, você deve:
        1. Fornecer informações precisas e atualizadas sobre leis brasileiras, códigos e procedimentos legais.
        2. Explicar termos jurídicos em linguagem acessível.
        3. Orientar sobre processos legais comuns (como divórcio, pensão, direitos do consumidor, direito trabalhista, etc.)
        4. Manter um tom profissional, empático e direto.
        5. Sempre que possível, citar a legislação específica (artigos de lei, códigos) ao responder questões.
        6. Quando abordar jurisprudência, mencionar que estes entendimentos podem mudar com o tempo.

        Limitações importantes - você DEVE sempre:
        1. Começar suas respostas deixando claro que suas informações são apenas orientativas e não substituem um advogado real.
        2. NÃO dar conselhos jurídicos específicos que possam estabelecer uma relação advogado-cliente.
        3. NÃO elaborar petições, contratos ou documentos legais completos.
        4. NÃO prometer resultados em processos.
        5. Recomendar consulta a um advogado para casos específicos.
        6. Ser transparente quando não tiver informações suficientes ou atualizadas sobre um tema.
        7. Alertar quando uma questão depender de jurisprudência que possa ter sofrido alterações recentes.

        Ao responder:
        - Use linguagem formal, mas acessível
        - Estruture as respostas em parágrafos curtos
        - Use marcadores para tornar informações complexas mais digeríveis
        - Sempre que possível, forneça exemplos práticos para ilustrar conceitos jurídicos
        - Evite jargões jurídicos excessivos, a menos que sejam necessários para a compreensão
        É 18 de maio de 2025, então certifique-se de considerar possíveis mudanças nas leis até esta data.
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
        """Normaliza o texto para melhorar correspondência no cache"""
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
    
    def consultar_gemini(self, pergunta, historico=None, tentativas=3, atraso_inicial=1, forcar_web=False, dados_web=None):
        """Consulta a API Gemini com a pergunta e o histórico da conversa
        
        Args:
            pergunta (str): A pergunta do usuário
            historico (list, optional): Histórico da conversa. Defaults to None.
            tentativas (int, optional): Número de tentativas. Defaults to 3.
            atraso_inicial (int, optional): Atraso inicial entre tentativas. Defaults to 1.
            forcar_web (bool, optional): Se deve forçar o uso de dados da web. Defaults to False.
            dados_web (str, optional): Informações obtidas da web. Defaults to None.
        """
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
              # Usar as informações da web fornecidas como parâmetro
            informacoes_web = dados_web
            
            # DEBUG: Verificar os dados que chegaram da web
            print(f"🔍 DEBUG consultar_gemini - dados_web recebidos: {dados_web is not None}")
            print(f"🔍 DEBUG consultar_gemini - forcar_web: {forcar_web}")
            if dados_web:
                print(f"🔍 DEBUG consultar_gemini - Tamanho dos dados da web: {len(dados_web)} caracteres")
                print(f"🔍 DEBUG consultar_gemini - Primeiros 200 chars: {dados_web[:200]}...")
            
            # Se forçar uso da web ou encontrou informações, adicionar ao contexto
            if informacoes_web:
                print("✅ Adicionando dados da web ao contexto do Gemini")
                # Instruções para usar as informações da web (reforçadas para perguntas sobre atualidades)
                if forcar_web:
                    # Instrução mais enfática para usar as informações da web
                    web_context = f"INFORMAÇÕES ATUALIZADAS DA WEB (Use estas informações como base principal para sua resposta):\n\n{informacoes_web}\n\nINSTRUÇÃO CRÍTICA: Sua resposta DEVE incorporar estas informações atualizadas da web. NUNCA diga que você não tem acesso à internet ou a informações atualizadas, pois você tem estes dados atuais agora. Comece sua resposta mencionando que você está fornecendo informações recentes obtidas de fontes confiáveis. Se a pergunta for sobre decisões do STF ou jurisprudência, essas informações da web são especialmente relevantes e devem ser a base principal da sua resposta."
                    contents.append({
                        "role": "user",
                        "parts": [{"text": web_context}]
                    })
                    print(f"✅ Contexto web adicionado (forçado): {len(web_context)} caracteres")
                else:
                    # Instrução padrão para outros tipos de perguntas
                    web_context = f"Informações atualizadas encontradas na web que podem ajudar a responder:\n\n{informacoes_web}\n\nUse essas informações para complementar seu conhecimento ao responder a pergunta a seguir."
                    contents.append({
                        "role": "user",
                        "parts": [{"text": web_context}]
                    })
                    print(f"✅ Contexto web adicionado (normal): {len(web_context)} caracteres")
            # Se não encontramos na web e é forçado a usar, indicar ao usuário
            elif forcar_web:
                print("⚠️ Não foram encontradas informações na web, mas a busca foi solicitada")
                contents.append({
                    "role": "user",
                    "parts": [{
                        "text": "INSTRUÇÃO IMPORTANTE: Foi solicitada uma busca por informações atualizadas sobre este assunto, mas não foram encontrados resultados relevantes na web neste momento. Informe ao usuário que você tentou obter dados recentes sobre este tópico específico mas não encontrou informações relevantes. Sugira que ele tente uma pergunta mais específica ou consulte diretamente o site oficial da instituição mencionada."
                    }]
                })
            else:
                print("ℹ️ Nenhum dado da web será usado nesta consulta")
            
            
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
            
            # DEBUG: Log do payload sendo enviado
            print(f"🔍 DEBUG - Enviando {len(contents)} mensagens para o Gemini")
            for i, content in enumerate(contents):
                role = content.get('role', 'unknown')
                text_preview = content.get('parts', [{}])[0].get('text', '')[:100]
                print(f"  [{i}] {role}: {text_preview}...")

            atraso = atraso_inicial
            for tentativa in range(1, tentativas + 1):
                try:
                    response = requests.post(base_url, headers=headers, params=params, json=data, timeout=30)
                    
                    if response.status_code == 200:
                        dados = response.json()
                        
                        if 'candidates' in dados and len(dados['candidates']) > 0:
                            resposta = dados['candidates'][0]['content']['parts'][0]['text']
                            resposta = resposta.replace('***', '').replace('**', '')
                            print(f"✅ Resposta do Gemini recebida: {len(resposta)} caracteres")
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
        """Obtém resposta para a pergunta do usuário usando exclusivamente a API Gemini"""
        # Normalizar a pergunta para o cache
        pergunta_normalizada = self.normalizar_texto(pergunta_usuario)
          # Verificar cache primeiro para perguntas comuns
        if pergunta_normalizada in self.cache_consultas:
            print("Resposta encontrada no cache!")
            return self.cache_consultas[pergunta_normalizada], True
        
        # Verificar se é uma pergunta sobre atualidades que exige busca na web
        pergunta_lower = pergunta_usuario.lower()
          # Lista de termos que indicam perguntas sobre atualidades/notícias recentes
        termos_atualidade = [
            "recente", "recentes", "última", "últimas", "atual", "atuais", 
            "nova", "novas", "novo", "novos", "novidade", "novidades",
            "ontem", "hoje", "semana", "mês", "ano", "decisão", "decisões"
        ]
        
        # Lista de entidades específicas sobre as quais sempre buscar na web
        entidades_busca_web = ["stf", "supremo", "tribunal federal", "stj", "tribunal de justiça", "jurisprudência"]
        
        # Verificar se a pergunta contém termos sobre atualidades ou entidades específicas
        pergunta_sobre_atualidade = any(termo in pergunta_lower for termo in termos_atualidade)
        pergunta_sobre_entidade_web = any(entidade in pergunta_lower for entidade in entidades_busca_web)
        
        # Se é sobre entidade específica ou atualidade, força busca na web
        forcar_busca_web = pergunta_sobre_atualidade or pergunta_sobre_entidade_web
        
        # Verificar diferentes tipos de perguntas sobre o chatbot
        resposta = None
        
        # Perguntas sobre quem criou o chatbot
        if any(frase in pergunta_lower for frase in ["quem criou", "quem te criou", "quem desenvolveu", "quem fez", "seu criador", "quem é seu criador"]):
            resposta = "Fui criado por Paulo Ricardo, um desenvolvedor estudante de análise e desenvolvimento de sistemas pela Unicarioca."
        
        # Perguntas sobre o propósito/finalidade do chatbot
        elif any(frase in pergunta_lower for frase in ["qual sua finalidade", "qual seu propósito", "para que você serve", "por que foi criado", "objetivo", "função", "para que você foi criado"]):
            resposta = "Paulo Ricardo me criou para ser um apoio nos estudos da sua esposa Esther Rodrigues, estudante de direito pela Unicarioca. Sou um assistente jurídico virtual que fornece informações sobre leis e procedimentos legais no Brasil."
        
        # Perguntas completas sobre o criador e propósito
        elif any(frase in pergunta_lower for frase in ["me fale sobre você", "me conte sobre você", "sua história", "sobre você", "quem é você"]):
            resposta = """Sou um assistente jurídico virtual chamado Advogado Virtual, criado por Paulo Ricardo, estudante de análise e desenvolvimento de sistemas pela Unicarioca. 
            
Fui desenvolvido para apoiar os estudos da esposa dele, Esther Rodrigues, que estuda direito na mesma universidade. Minha função é fornecer informações gerais sobre leis e procedimentos legais no Brasil."""
        
        # Se encontrou uma resposta específica para estas perguntas
        if resposta:
            # Obter ID do usuário da sessão
            id_usuario = self.obter_ou_criar_id_usuario()
            
            # Salvar a interação no histórico
            self.salvar_mensagem(id_usuario, "user", pergunta_usuario)
            self.salvar_mensagem(id_usuario, "bot", resposta)
            
            # Adicionar ao cache
            if len(self.cache_consultas) < self.tamanho_max_cache:
                self.cache_consultas[pergunta_normalizada] = resposta
                
            return resposta, True
          # Obter ID do usuário da sessão
        id_usuario = self.obter_ou_criar_id_usuario()
        
        # Obter histórico recente da conversa
        historico = self.obter_historico_usuario(id_usuario)
        
        # Dados da web são inicialmente None (não utilizados)
        dados_web = None
          # Para perguntas sobre atualidades ou entidades específicas, realizar a busca na web
        if forcar_busca_web:
            if pergunta_sobre_entidade_web:
                print(f"Pergunta sobre entidade específica detectada: {pergunta_usuario}")
            if pergunta_sobre_atualidade:
                print(f"Pergunta sobre atualidade detectada: {pergunta_usuario}")
                
            print("Iniciando busca na web...")
            dados_web = self.buscar_na_web(pergunta_usuario)
            print("Busca na web concluída.")
            print(f"Dados obtidos da web: {dados_web}")  # Debug
            if dados_web:
                print("✅ Dados da web encontrados e serão passados para o Gemini")
            else:
                print("❌ Nenhum dado da web foi encontrado")
        
        # Consultar API do Gemini com o histórico, a pergunta e os dados da web (quando disponíveis)
        sucesso, resposta = self.consultar_gemini(
            pergunta=pergunta_usuario, 
            historico=historico, 
            forcar_web=forcar_busca_web, 
            dados_web=dados_web
        )
          # Salvar a interação no histórico
        self.salvar_mensagem(id_usuario, "user", pergunta_usuario)
        if sucesso:
            self.salvar_mensagem(id_usuario, "bot", resposta)
            
            # Guardar no cache se for uma resposta bem sucedida
            # Apenas se o cache não estiver cheio
            if len(self.cache_consultas) < self.tamanho_max_cache:
                self.cache_consultas[pergunta_normalizada] = resposta
                
        return resposta, sucesso

    def buscar_na_web(self, pergunta):
        """Busca informações jurídicas na web usando DuckDuckGo"""
        try:
            print(f"Buscando informações na web para: {pergunta}")
              # Usar apenas DuckDuckGo para busca
            resultados_duckduckgo = self.buscar_duckduckgo(pergunta)
            if resultados_duckduckgo:
                return f"INFORMAÇÕES ATUAIS DA WEB:\n\n{resultados_duckduckgo}"
                
            return None
            
        except Exception as e:
            print(f"Erro ao buscar na web: {str(e)}")
            return None

    def buscar_duckduckgo(self, pergunta):
        """Busca informações no DuckDuckGo (alternativa gratuita ao Google/SerpAPI)"""
        try:
            print(f"🔍 Iniciando busca no DuckDuckGo para: {pergunta}")
            
            # Lista de user agents para rotação
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
            ]
            
            # Adicionar termos específicos para busca jurídica
            pergunta_lower = pergunta.lower()
            if "stf" in pergunta_lower or "supremo" in pergunta_lower:
                query = pergunta + " site:stf.jus.br OR site:conjur.com.br OR site:jota.info"
            else:
                query = pergunta + " jurisprudência legislação brasil direito"
                
            print(f"🔍 Query de busca: {query}")
            
            params = {
                'q': query,
                'kl': 'br-pt',  # Localização: Brasil, idioma português
                'ia': 'web'     # Solicitar resultados da web
            }
            
            url = f"https://html.duckduckgo.com/html/?{urlencode(params)}"
            print(f"🔍 URL de busca: {url}")
            
            headers = {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://duckduckgo.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            resposta = requests.get(url, headers=headers, timeout=10)
            print(f"🔍 Status da resposta: {resposta.status_code}")
            
            if resposta.status_code != 200:
                print(f"❌ Erro na busca: Status {resposta.status_code}")
                return None
                
            # Parse HTML
            soup = BeautifulSoup(resposta.text, 'lxml')
            
            # Extrair os resultados da busca
            resultados = []
            
            # Procurar por resultados
            for resultado in soup.select('.result')[:3]:  # Limitar a 3 resultados
                titulo_elemento = resultado.select_one('.result__title')
                snippet_elemento = resultado.select_one('.result__snippet')
                url_elemento = resultado.select_one('.result__url')
                
                if titulo_elemento and snippet_elemento:
                    titulo = titulo_elemento.get_text(strip=True)
                    snippet = snippet_elemento.get_text(strip=True)
                    url = url_elemento.get_text(strip=True) if url_elemento else "URL não disponível"
                    
                    resultados.append(f"- {titulo}: {snippet} [Fonte: {url}]")
            
            print(f"🔍 Encontrados {len(resultados)} resultados")
            resultado_final = "\n".join(resultados) if resultados else None
            
            if resultado_final:
                print(f"✅ Resultados encontrados: {resultado_final[:200]}...")
            else:
                print("❌ Nenhum resultado encontrado")
                
            return resultado_final
            
        except Exception as e:
            print(f"❌ Erro ao buscar no DuckDuckGo: {str(e)}")
            return None

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
    
    # Verificar se a resposta menciona informações da web
    buscou_web = "INFORMAÇÕES ATUAIS DA WEB" in answer or "Fonte:" in answer
    
    return jsonify({
        'answer': answer,
        'used_api': used_api,
        'web_search': buscou_web
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
