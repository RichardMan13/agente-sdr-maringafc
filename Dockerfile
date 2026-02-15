# Imagem base leve e estável
FROM python:3.11-slim

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema necessárias para pacotes como numpy/pandas
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar apenas o requirements primeiro (Otimização de Cache)
COPY requirements.txt .

# Instalar as dependências do Python conforme seu arquivo estruturado
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o restante do código do projeto
COPY . .

# Comando para iniciar o agente
# Como você usa LangGraph, aqui você pode iniciar um script de interface ou API
CMD ["python", "src/agent.py"]