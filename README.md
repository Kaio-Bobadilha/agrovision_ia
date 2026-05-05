# AgroVision IA

Sistema de monitoramento visual com IA local para detecção de objetos em tempo real usando YOLO11 e chat com Llama via Ollama.

## Funcionalidades

- **Câmera ao vivo**: Streaming MJPEG da câmera com detecção automática.
- **Detecção de objetos**: Usa YOLO11 para detectar pessoas e veículos.
- **Banco de dados**: Eventos salvos em SQLite com capturas de imagem.
- **Chat com IA**: Perguntas respondidas pelo TinyLlama local via Ollama.
- **Dashboard moderno**: Interface web responsiva com métricas e eventos recentes.

## Pré-requisitos

- Python 3.11+
- Ollama instalado (https://ollama.ai/)
- Webcam conectada

## Instalação

1. Clone ou baixe o projeto.
2. Crie e ative o ambiente virtual:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1  # Windows
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. Instale o Ollama e baixe o modelo:
   ```bash
   ollama pull tinyllama
   ```

## Execução

### Opção 1: Script PowerShell (Recomendado)
```bash
.\run.ps1 -Foreground
```

### Opção 2: Manual
1. Inicie o Ollama:
   ```bash
   ollama serve
   ```
2. Execute o FastAPI:
   ```bash
   .\.venv\Scripts\Activate.ps1
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
   ```

## Acesso

Abra http://127.0.0.1:8001 no navegador.

## Estrutura do Projeto

```
agrovision_ia/
├── .venv/              # Ambiente virtual
├── app/
│   ├── main.py         # Aplicação FastAPI
│   ├── templates/
│   │   └── index.html  # Dashboard
│   └── static/
│       ├── dashboard.css
│       └── chat.js
├── requirements.txt    # Dependências
├── run.ps1            # Script de execução
└── README.md          # Este arquivo
```

## Endpoints

- `GET /`: Dashboard principal
- `POST /upload`: Upload de imagem para detecção
- `GET /video_feed`: Stream MJPEG da câmera
- `GET /health`: Status do sistema e Ollama
- `POST /chat`: Chat com resposta completa
- `POST /chat/stream`: Chat com streaming

## Configuração

Variáveis de ambiente opcionais:
- `OLLAMA_URL`: URL do Ollama (padrão: http://127.0.0.1:11434/api/chat)
- `OLLAMA_MODEL`: Modelo do Ollama (padrão: llama3)
- `OLLAMA_TIMEOUT`: Timeout em segundos (padrão: 120)

## Desenvolvimento

Para contribuir:
1. Faça mudanças no código.
2. Teste localmente.
3. Atualize o README se necessário.

## Próximas Melhorias

- Histórico persistente de conversa.
- Escolha de modelo via interface.
- Configurações avançadas.
- Suporte a múltiplas câmeras.