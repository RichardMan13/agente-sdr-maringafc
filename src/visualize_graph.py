from src.agent import dogao_agent
import sys

def generate_graph_image():
    try:
        print("Gerando imagem da arquitetura do agente...")
        # Obtém a representação binária do PNG
        png_data = dogao_agent.get_graph().draw_mermaid_png()
        
        output_file = "agent_architecture.png"
        with open(output_file, "wb") as f:
            f.write(png_data)
            
        print(f"Imagem salva com sucesso em: {output_file}")
    except Exception as e:
        print(f"Erro ao gerar imagem: {e}")
        # Tenta imprimir o mermaid text caso falhe a geração da imagem (ex: falta de dependências)
        try:
            print("Tentando exibir o código Mermaid:")
            print(dogao_agent.get_graph().draw_mermaid())
        except:
            pass

if __name__ == "__main__":
    generate_graph_image()
