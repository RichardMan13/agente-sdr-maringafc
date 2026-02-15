from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def processar_documentos(file_path):
    # 1. Carregar o arquivo .txt específico
    loader = TextLoader(file_path, encoding='utf-8')
    documentos = loader.load()

    # 2. Configurar o Splitter
    # chunk_size: tamanho aproximado do bloco (tokens/caracteres)
    # chunk_overlap: "janela" de repetição para não perder contexto entre blocos
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        separators=["\n===", "\n\n", "\n", " "]
    )

    # 3. Gerar os chunks
    chunks = text_splitter.split_documents(documentos)
    
    print(f"✅ Processamento concluído para {file_path}: {len(chunks)} fragmentos gerados.")
    return chunks

if __name__ == "__main__":
    # Exemplo de uso
    import os
    # Pega um arquivo de exemplo se existir
    files = [f for f in os.listdir('./data/raw') if f.endswith('.txt')]
    if files:
        processar_documentos(os.path.join('./data/raw', files[0]))