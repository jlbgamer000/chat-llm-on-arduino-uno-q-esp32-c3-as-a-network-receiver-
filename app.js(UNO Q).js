// SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
// SPDX-License-Identifier: MPL-2.0

const socket = io(`http://${window.location.host}`);

let thinkingMessageElement = null;
let sendButton;
let sendButtonImg;
let quickActionButtonsContainer;
let customPlaceholder;
let lastUserPrompt = '';

function showError(message) {
    console.log(message);
    const errorBanner = document.getElementById('error-banner');
    const errorMessage = document.getElementById('error-message');
    if (errorBanner && errorMessage) {
        errorMessage.textContent = message;
        errorBanner.style.display = 'block';
    }
}

function hideError() {
    const errorBanner = document.getElementById('error-banner');
    if (errorBanner) {
        errorBanner.style.display = 'none';
    }
}

function removeThinkingMessage() {
    if (thinkingMessageElement && thinkingMessageElement.parentNode) {
        thinkingMessageElement.parentNode.removeChild(thinkingMessageElement);
        thinkingMessageElement = null;
    }
}

function handleResponse(data) {
    const ai_msg = document.getElementById('active-ai-response');
    if (thinkingMessageElement) {
        const textContent = thinkingMessageElement.querySelector('.text-content');
        if (textContent) {
            textContent.innerHTML = '';
        }
        thinkingMessageElement.classList.remove('thinking-message');
        thinkingMessageElement.dataset.rawText = '';
        thinkingMessageElement = null;
    }

    if (ai_msg) {
        ai_msg.dataset.rawText += data;
        const textContent = ai_msg.querySelector('.text-content');
        if (textContent) {
            textContent.innerHTML = marked.parse(ai_msg.dataset.rawText);
        }
    }
}

function handleStreamEnd() {
    removeThinkingMessage();
    const ai_msg = document.getElementById('active-ai-response');
    if (ai_msg) {
        ai_msg.id = '';
    }
    if (sendButton) {
        sendButton.classList.remove('sending-state');
        if (sendButtonImg) {
            sendButtonImg.src = 'img/send.svg';
        }
    }
    updateSendButtonState();
    updateClearChatButtonState();
}

function autoExpandInput(element) {
    element.style.height = 'auto';
    element.style.height = (element.scrollHeight) + 'px';
}

function updatePlaceholderVisibility() {
    const userInput = document.getElementById('user-input');
    if (userInput && customPlaceholder) {
        customPlaceholder.style.display = userInput.value ? 'none' : 'block';
    }
}

function updateSendButtonState() {
    const userInput = document.getElementById('user-input');
    if (sendButton && userInput) {
        if (userInput.value.trim() !== '') {
            sendButton.classList.add('active');
            sendButton.removeAttribute('disabled');
        } else {
            sendButton.classList.remove('active');
            sendButton.setAttribute('disabled', 'true');
        }
    }
}

function updateClearChatButtonState() {
    const clearChatButton = document.getElementById('clear-chat-button-header');
    const chatMessagesContainer = document.getElementById('chat-messages-container');
    if (clearChatButton && chatMessagesContainer) {
        if (chatMessagesContainer.children.length > 0 && !document.getElementById('empty-chat-container')) {
            clearChatButton.classList.remove('disabled');
        } else {
            clearChatButton.classList.add('disabled');
        }
    }
}

function appendMessage(sender, message) {
    const chatMessagesContainer = document.getElementById('chat-messages-container');
    const emptyChatContainer = document.getElementById('empty-chat-container');

    if (emptyChatContainer) {
        emptyChatContainer.remove();
    }

    const messageElement = document.createElement('div');
    messageElement.classList.add('chat-message', `${sender}-message`);

    const textElement = document.createElement('div');
    textElement.classList.add('text-content');

    if (sender === 'user') {
        textElement.textContent = message;
        messageElement.appendChild(textElement);
    } else {
        messageElement.id = 'active-ai-response';
        messageElement.dataset.rawText = '';
        messageElement.appendChild(textElement);
    }

    chatMessagesContainer.appendChild(messageElement);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    return messageElement;
}

function sendMessage(prompt) {
    if (!prompt || prompt.trim() === '') return;

    hideError();
    appendMessage('user', prompt);

    thinkingMessageElement = appendMessage('ai', '');
    thinkingMessageElement.classList.add('thinking-message');
    const textContent = thinkingMessageElement.querySelector('.text-content');
    if (textContent) {
        textContent.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    }

    socket.emit('prompt', { prompt: prompt });

    const userInput = document.getElementById('user-input');
    if (userInput) {
        userInput.value = '';
        userInput.style.height = 'auto';
        updatePlaceholderVisibility();
        updateSendButtonState();
    }

    if (sendButton) {
        sendButton.classList.add('sending-state');
        if (sendButtonImg) {
            sendButtonImg.src = 'img/stop.svg';
        }
    }
}

function sendClearChatCommand() {
    socket.emit('commands', { command: 'clear_chat' });
}

function sendStopStreamCommand() {
    socket.emit('commands', { command: 'stop_stream' });
}

socket.on('response', handleResponse);
socket.on('stream_end', handleStreamEnd);

socket.on('llm_error', (data) => {
    removeThinkingMessage();
    showError(`LLM error: ${data.error}`);
    handleStreamEnd();
});

socket.on('command_ok', (data) => {
    if (data.command === 'clear_chat') {
        const chatMessagesContainer = document.getElementById('chat-messages-container');
        chatMessagesContainer.innerHTML = `
            <div id=\"empty-chat-container\">
                <div class=\"icon-and-greeting\">
                    <img src=\"img/green-stars.svg\" alt=\"Green Stars\" />
                    <p class=\"greeting\">Good morning</p>
                    <p class=\"prompt-question\">What can I help you with today?</p>
                </div>
            </div>`;
        updateClearChatButtonState();
    }
});

document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    sendButton = document.getElementById('send-button');
    sendButtonImg = sendButton ? sendButton.querySelector('img') : null;
    customPlaceholder = document.querySelector('.custom-placeholder');
    quickActionButtonsContainer = document.getElementById('quick-action-buttons');
    const clearChatButton = document.getElementById('clear-chat-button-header');

    if (userInput) {
        userInput.addEventListener('input', () => {
            autoExpandInput(userInput);
            updatePlaceholderVisibility();
            updateSendButtonState();
        });

        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (sendButton && !sendButton.disabled && !sendButton.classList.contains('sending-state')) {
                    sendMessage(userInput.value);
                }
            }
        });
    }

    if (sendButton) {
        sendButton.addEventListener('click', () => {
            if (sendButton.classList.contains('sending-state')) {
                sendStopStreamCommand();
            } else {
                sendMessage(userInput.value);
            }
        });
    }

    if (clearChatButton) {
        clearChatButton.addEventListener('click', sendClearChatCommand);
    }
});