async function sendQuestion() {
    const questionInput = document.getElementById('chat-question');
    const sendButton = document.getElementById('chat-send-button');
    const statusDiv = document.getElementById('chat-status');
    const responseDiv = document.getElementById('chat-response');

    const message = questionInput.value.trim();
    if (!message) return;

    // Desabilitar botão e atualizar status
    sendButton.disabled = true;
    statusDiv.textContent = 'Consultando o modelo local...';
    responseDiv.textContent = '';

    const startedAt = Date.now();

    try {
        // Tentar streaming primeiro
        const response = await fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, history: [] })
        });

        if (response.ok) {
            await readStreamedChat(response, responseDiv, statusDiv, startedAt);
        } else {
            // Fallback para resposta completa
            await fallbackChat(message, responseDiv, statusDiv, startedAt);
        }
    } catch (error) {
        statusDiv.textContent = 'Erro: ' + error.message;
    } finally {
        sendButton.disabled = false;
        questionInput.value = '';
    }
}

async function readStreamedChat(response, responseBox, statusBox, startedAt) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';
    let firstWordReceived = false;

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.content) {
                            if (!firstWordReceived) {
                                const timeToFirst = Date.now() - startedAt;
                                statusBox.textContent = `Resposta iniciada em ${timeToFirst}ms...`;
                                firstWordReceived = true;
                            }
                            fullResponse += data.content;
                            responseBox.textContent = fullResponse;
                        }
                    } catch (e) {
                        // Ignorar linhas inválidas
                    }
                }
            }
        }

        const totalTime = Date.now() - startedAt;
        statusBox.textContent = `Resposta completa em ${totalTime}ms. Pronto para nova pergunta.`;
    } catch (error) {
        statusBox.textContent = 'Erro no streaming: ' + error.message;
    }
}

async function fallbackChat(message, responseBox, statusBox, startedAt) {
    const response = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, history: [] })
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const totalTime = Date.now() - startedAt;
    responseBox.textContent = data.answer;
    statusBox.textContent = `Resposta completa em ${totalTime}ms. Pronto para nova pergunta.`;
}

// Permitir envio com Enter
document.getElementById('chat-question').addEventListener('keypress', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendQuestion();
    }
});