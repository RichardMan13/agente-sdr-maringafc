# ⚽ Agente SDR Inteligente - Maringá FC

Este projeto consiste no desenvolvimento de um agente de IA especializado em atendimento e vendas (SDR/SAC Nível 1) para o **Maringá Futebol Clube**. O sistema utiliza arquitetura **RAG (Retrieval-Augmented Generation)** para fornecer respostas precisas baseadas em dados reais do clube, garantindo uma transição fluida entre infraestruturas de nuvem.

## 🎯 Desafio
Converter interessados em sócios-torcedores através de uma base de conhecimento dinâmica, mantendo a resiliência técnica durante a migração de infraestrutura da **AWS para Azure**.

---

## 🛠️ Stack Tecnológica
- **Linguagem:** Python (Pandas, Scikit-learn, LangChain)
- **Banco de Dados:** Supabase (PostgreSQL + pgvector)
- **Orquestração:** Prefect
- **Infraestrutura:** Docker, AWS (atual) e Azure (destino)
- **IA:** OpenAI API (Embeddings e LLM)

---

## 📋 Plano de Execução Técnica

### Fase 1: Camada de Dados e Vetorização (Supabase + Hybrid Search)
O Supabase atua como o core da persistência e busca semântica.
* **Armazenamento:** Utilização do `pgvector` para armazenar embeddings de manuais, planos e FAQs do clube.
* **Pipeline de Ingestão:** Script em Python para realizar o *chunking* de documentos e geração de vetores.
* **Data Quality:** Implementação de checks de qualidade para evitar o uso de planos ou preços obsoletos.

### Fase 2: Orquestração e Lógica do Agente (LangChain / CrewAI)
Desenvolvimento da inteligência e comportamento do bot.
* **Fluxo de RAG:** Cadeia de busca otimizada para reduzir o consumo de tokens e aumentar a precisão.
* **Identificação de Intenção:** Modelos de classificação para distinguir entre "Dúvidas de SAC" e "Oportunidades de Venda".
* **Memória de Curto Prazo:** Persistência do histórico da conversa para manter o contexto do torcedor.

### Fase 3: Infraestrutura e Migração (AWS ➡️ Azure)
O diferencial estratégico focado em disponibilidade e escalabilidade.
* **Estado Atual (AWS):** Execução via AWS Lambda/ECS orquestrada por Prefect.
* **Dockerização:** Containerização completa para garantir paridade entre os ambientes de nuvem.
* **Estratégia de Migração:** Deploy automatizado via CI/CD para Azure App Service/Functions com foco em zero downtime.

## ✅ Status do Projeto & Checklist Técnico

Acompanhamento em tempo real das etapas de desenvolvimento do agente.

### 🏁 Fase 1: Camada de Dados e Vetorização
- [x] **Database Setup:** Extensão `pgvector` habilitada e tabelas criadas no Supabase.
- [x] **Ambiente Local:** Configuração de `.gitignore`, `requirements.txt` e conexão validada.
- [x] **Data Curation:** Extração manual de Sócio, Ingressos, FAQ e Pontos de Venda em arquivos .txt.
- [x] **Document Processing:** Lógica de *chunking* para fragmentação semântica dos planos de sócio.
- [x] **Vectorization Pipeline:** Integração com OpenAI para geração de embeddings (1536d).
- [x] **Data Ingestion:** Script de carga automatizada para o banco vetorial.

### 🤖 Fase 2: Orquestração e Lógica do Agente
- [x] **RAG Chain:** Implementação da busca por similaridade via LangChain.
- [x] **Prompt Engineering:** Definição da persona SDR e diretrizes de comportamento.
- [x] **Intent Classification:** Lógica para separar leads de vendas de dúvidas de SAC.
- [x] **Memory Management:** Histórico de conversa persistido para manutenção de contexto.
- [x] **SDR Tracking:** Gatilhos para salvamento de novos leads na tabela `leads_sdr`.

### ☁️ Fase 3: Infraestrutura e Migração (AWS ➡️ Azure)
- [x] **Dockerization:** Criação de Dockerfile para portabilidade entre nuvens.
- [ ] **Prefect Cloud:** Orquestração dos fluxos de atualização de dados (ETL).
- [ ] **Azure Resource Setup:** Provisionamento de App Service/Functions para o backend.
- [ ] **CI/CD Pipeline:** GitHub Actions configurado para deploy automatizado na Azure.
- [ ] **Final Validation:** Testes de carga e validação de latência pós-migração.

---

## 🏗️ Arquitetura do Banco de Dados
O modelo segue uma estrutura otimizada para busca vetorial e gestão de leads.

[Insira aqui o link ou imagem do seu diagrama do dbdiagram.io]

---

## 🚀 Como Executar
1. Clone o repositório.
2. Configure o arquivo `.env` com suas credenciais do Supabase e OpenAI.
3. Instale as dependências: `pip install -r requirements.txt`.
4. Execute o pipeline de ingestão: `python src/ingestion.py`.