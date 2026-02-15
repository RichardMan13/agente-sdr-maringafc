import os
from dotenv import load_dotenv
from supabase import create_client
from langchain_openai import OpenAIEmbeddings
from processing import processar_documentos # Importa a lógica anterior
import glob

# 1. Configurações Iniciais
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

def ingestao_vetorial(file_path):
    print(f"🚀 Iniciando vetorização para o arquivo: {file_path} e upload para o Supabase: {SUPABASE_URL}")

    # 2. Obter os chunks processados para o arquivo único
    chunks = processar_documentos(file_path)
    
    if not chunks:
        print(f"⚠️  Nenhum chunk gerado para {file_path}.")
        return None

    # 3. Limpar base de conhecimento antiga (Opcional, mas recomendado para testes)
    # supabase.table("conhecimento_clube").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    records = []
    for chunk in chunks:
        # Gerar o vetor para o conteúdo do chunk
        vector = embeddings_model.embed_query(chunk.page_content)
        
        # Extrair metadados (nome do arquivo define a categoria)
        file_name = os.path.basename(file_path)
        categoria = file_name.replace('.txt', '')
        
        records.append({
            "categoria": categoria,
            "conteudo": chunk.page_content,
            "embedding": vector,
            "fonte_url": "https://maringafc.com.br"
        })

    # 4. Upload em lote (Batch Insert)
    result = supabase.table("conhecimento_clube").insert(records).execute()
    
    print(f"✅ Sucesso! {len(records)} registros vetorizados e inseridos para {file_path}.")
    return result

def main():
    files = glob.glob("./data/raw/*.txt")
    if not files:
        print("⚠️ Nenhum arquivo .txt encontrado em ./data/raw")
        return

    for file_path in files:
        # Normalizar caminho para evitar problemas com barras invertidas no Windows
        normalized_path = file_path.replace("\\", "/")
        ingestao_vetorial(normalized_path)

if __name__ == "__main__":
    main()