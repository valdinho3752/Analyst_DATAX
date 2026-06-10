document.addEventListener('DOMContentLoaded', () => {
    const inputField = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const chatHistory = document.getElementById('chat-history');
    const typingIndicator = document.getElementById('typing-indicator');

    // Auto-resize textarea
    inputField.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if(this.value === '') this.style.height = 'auto';
    });

    // Send on Enter (but allow Shift+Enter for new line)
    inputField.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    async function sendMessage() {
        const text = inputField.value.trim();
        if (!text) return;

        // Reset input
        inputField.value = '';
        inputField.style.height = 'auto';

        // Add User Message
        appendMessage(text, 'user');

        // Show loading
        typingIndicator.classList.remove('hidden');
        chatHistory.scrollTop = chatHistory.scrollHeight;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query: text })
            });

            if (!response.ok) {
                throw new Error("Error en la conexión con el servidor");
            }

            const data = await response.json();
            
            // Extraer el texto de la respuesta A2A
            let agentText = "Lo siento, no pude procesar la respuesta.";
            
            if (data.result && data.result.parts) {
                // Formato directo (Message)
                for (let part of data.result.parts) {
                    if (part.text) {
                        agentText = part.text;
                        break;
                    } else if (part.root && part.root.text) {
                        agentText = part.root.text;
                        break;
                    }
                }
            } else if (data.result && data.result.content && data.result.content.parts) {
                // Formato anidado (MessageInfo con content)
                for (let part of data.result.content.parts) {
                    if (part.root && part.root.text) {
                        agentText = part.root.text;
                        break;
                    } else if (part.text) {
                        agentText = part.text;
                        break;
                    }
                }
            } else if (data.error) {
                agentText = `Error Interno: ${data.error}`;
            }

            if (agentText) {
                agentText = agentText.replace(/\]\(\/reports\//g, '](http://localhost:8000/reports/');
            }

            appendMessage(agentText, 'system');

        } catch (error) {
            appendMessage(`Error: ${error.message}. Asegúrate de que el Host Agent esté encendido en el puerto 10002.`, 'system');
        } finally {
            typingIndicator.classList.add('hidden');
        }
    }

    function appendMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', `${sender}-message`, 'fade-in');

        const avatarIcon = sender === 'user' ? 'user' : 'bot';
        
        // Parse markdown if system
        const htmlContent = sender === 'system' ? marked.parse(text) : escapeHtml(text);

        msgDiv.innerHTML = `
            <div class="avatar ${sender}-avatar">
                <i data-lucide="${avatarIcon}"></i>
            </div>
            <div class="message-bubble">
                ${htmlContent}
            </div>
        `;

        // Asegurar que los enlaces a PDF se abran en otra pestaña y fuercen la descarga
        if (sender === 'system') {
            const pdfLinks = msgDiv.querySelectorAll('a[href$=".pdf"]');
            pdfLinks.forEach(link => {
                let href = link.getAttribute('href');
                // Si el href tiene el esquema sandbox:, removerlo
                if (href && href.startsWith('sandbox:')) {
                    href = href.replace('sandbox:', '');
                }
                
                // Determinar el origen correcto (si es sandbox o null, usar http://localhost:8000)
                let baseOrigin = window.location.origin;
                if (!baseOrigin || baseOrigin.startsWith('sandbox') || baseOrigin === 'null' || !baseOrigin.startsWith('http')) {
                    baseOrigin = 'http://localhost:8000';
                }

                // Si el href es una ruta relativa absoluta, forzar la URL completa
                if (href && href.startsWith('/')) {
                    href = baseOrigin + href;
                } else if (href && !href.startsWith('http')) {
                    href = baseOrigin + '/' + href;
                }
                
                link.setAttribute('href', href);
                link.setAttribute('target', '_blank');
                link.setAttribute('download', '');
            });
        }

        chatHistory.appendChild(msgDiv);
        lucide.createIcons();
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    // Interceptar clicks en enlaces a PDF para evitar bloqueos del sandbox del IDE
    document.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (link) {
            const hrefAttr = link.getAttribute('href') || '';
            const hrefProp = link.href || '';
            
            if (hrefAttr.endsWith('.pdf') || hrefProp.endsWith('.pdf')) {
                e.preventDefault();
                
                let cleanedPath = hrefAttr;
                if (cleanedPath.startsWith('sandbox:')) {
                    cleanedPath = cleanedPath.replace('sandbox:', '');
                }
                
                // Determinar el origen correcto (usar http://localhost:8000 de fallback)
                let baseOrigin = window.location.origin;
                if (!baseOrigin || baseOrigin.startsWith('sandbox') || baseOrigin === 'null' || !baseOrigin.startsWith('http')) {
                    baseOrigin = 'http://localhost:8000';
                }
                
                // Asegurar URL absoluta
                let targetUrl = cleanedPath;
                if (cleanedPath.startsWith('/')) {
                    targetUrl = baseOrigin + cleanedPath;
                } else if (!cleanedPath.startsWith('http')) {
                    targetUrl = baseOrigin + '/' + cleanedPath;
                }
                
                console.log("Redirigiendo click de PDF a:", targetUrl);
                window.open(targetUrl, '_blank');
            }
        }
    });
});
