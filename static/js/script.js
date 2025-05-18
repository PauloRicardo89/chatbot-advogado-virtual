document.addEventListener("DOMContentLoaded", function () {
  const chatMessages = document.getElementById("chat-messages");
  const userInput = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const typingIndicator = document.getElementById("typing-indicator");
  const feedbackContainer = document.getElementById("feedback-container");
  const yesBtn = document.getElementById("yes-btn");
  const noBtn = document.getElementById("no-btn");

  let lastQuestion = "";
  let lastAnswer = "";
  let usedAPI = false;

  // Focar no input ao carregar a página
  userInput.focus();

  // Enviar mensagem ao clicar no botão ou pressionar Enter
  sendBtn.addEventListener("click", sendMessage);
  userInput.addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
      sendMessage();
    }
  });

  // Configurar botões de feedback
  yesBtn.addEventListener("click", function () {
    sendFeedback(true);
  });

  noBtn.addEventListener("click", function () {
    sendFeedback(false);
  });

  function sendMessage() {
    const message = userInput.value.trim();
    if (message === "") return;

    // Esconder feedback da resposta anterior
    feedbackContainer.style.display = "none";

    // Adicionar mensagem do usuário
    addMessage(message, "user");

    // Limpar input
    userInput.value = "";
    userInput.focus();

    // Mostrar indicador de digitação
    typingIndicator.style.display = "block";
    chatMessages.appendChild(typingIndicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Salvar última pergunta
    lastQuestion = message;

    // Fazer requisição para a API
    fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question: message }),
    })
      .then((response) => response.json())
      .then((data) => {
        // Esconder indicador de digitação
        typingIndicator.style.display = "none";

        // Adicionar resposta do bot
        addMessage(data.answer, "bot");

        // Salvar última resposta
        lastAnswer = data.answer;
        usedAPI = data.used_api;

        // Mostrar opções de feedback apenas se usou API
        if (usedAPI) {
          feedbackContainer.style.display = "flex";
        }
      })
      .catch((error) => {
        console.error("Erro:", error);
        typingIndicator.style.display = "none";
        addMessage(
          "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.",
          "bot"
        );
      });
  }

  function addMessage(text, sender) {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", sender);

    const contentDiv = document.createElement("div");
    contentDiv.classList.add("message-content");
    contentDiv.textContent = text;

    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);

    // Rolar para o final da conversa
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function sendFeedback(isHelpful) {
    // Ocultar container de feedback
    feedbackContainer.style.display = "none";

    // Enviar feedback para o servidor
    fetch("/api/feedback", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question: lastQuestion,
        answer: lastAnswer,
        is_helpful: isHelpful,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        // Adicionar mensagem de agradecimento
        const thankMessage = isHelpful
          ? "Obrigado pelo feedback positivo! Sua opinião ajuda a melhorar nossas respostas."
          : "Obrigado pelo feedback! Continuaremos melhorando nossas respostas.";

        addMessage(thankMessage, "bot");
      })
      .catch((error) => {
        console.error("Erro ao enviar feedback:", error);
      });
  }
});
