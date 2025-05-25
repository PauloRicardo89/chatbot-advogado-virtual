# Advogado Virtual - Chatbot Jurídico

Um assistente virtual jurídico que utiliza a API Gemini para fornecer informações e orientações sobre leis e procedimentos legais no Brasil.

## Características

- **Interface de Chat Amigável**: Interface web intuitiva que permite interações naturais com o chatbot.
- **Processamento de Linguagem Natural**: Utiliza a API Gemini do Google para compreender e responder às perguntas jurídicas.
- **Busca em Fontes Jurídicas**: Busca informações atualizadas em sites como JusBrasil, STF e STJ para fornecer respostas mais precisas e atualizadas.
- **Histórico de Conversas**: Salva automaticamente o histórico de todas as interações para referência futura.
- **Cache Inteligente**: Armazena respostas para perguntas frequentes, reduzindo o tempo de resposta.
- **Preparado para WhatsApp**: Estrutura base para integração com WhatsApp Business API.

## Configuração

### Pré-requisitos

- Python 3.9 ou superior
- Flask e suas dependências
- API Key do Google Gemini

### Instalação

1. Clone este repositório:

```
git clone https://github.com/seu-usuario/chatbot-advogado-web.git
cd chatbot-advogado-web
```

2. Instale as dependências:

```
pip install -r requirements.txt
```

3. Configure a chave API Gemini:
   - Opção recomendada: Defina a variável de ambiente `GEMINI_API_KEY`
   - Alternativa: Crie um arquivo `api-gemini.txt` na raiz do projeto contendo apenas a chave da API

## Uso

1. Execute o servidor:

```
python app.py
```

2. Acesse o chatbot:
   - No seu computador: http://127.0.0.1:5000/
   - Em dispositivos na mesma rede: http://[SEU_IP_LOCAL]:5000/

## Limitações

- O chatbot fornece apenas informações orientativas e NÃO substitui um advogado real.
- As informações jurídicas podem mudar com o tempo, e o chatbot tenta considerar as atualizações até a data configurada.
- Não elabora petições ou documentos legais completos.

## Funcionalidade de Busca na Web

O chatbot busca informações atualizadas em várias fontes:

1. **JusBrasil**: Para artigos e notícias jurídicas recentes
2. **STF/STJ**: Para jurisprudência e decisões de tribunais superiores
3. **DuckDuckGo**: Para pesquisas gerais em sites jurídicos

Quando o chatbot encontra informações relevantes na web, ele exibe uma indicação visual "Com dados da web" junto à resposta.

## Segurança

- NÃO inclua o arquivo `api-gemini.txt` no controle de versão!
- Em produção, use sempre variáveis de ambiente para armazenar chaves e tokens sensíveis.

## Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo LICENSE para detalhes.

## Contato

Para dúvidas ou sugestões, entre em contato através de pr.pauloricardo@live.com
