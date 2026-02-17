import requests
import json
import sys

# URL do endpoint da Azure
URL = "https://agente-sdr-maringafc-dva6guc5gkbxe3fs.brazilsouth-01.azurewebsites.net/chat"

def main():
    print("=== Simulador de Conversa com Agente SDR Maringá FC ===")
    print(f"Conectando a: {URL}")
    print("Para sair, digite 'sair', 'exit' ou pressione Ctrl+C.\n")

    # ID fictício para simular o usuário no WhatsApp
    # O agente usa esse ID para manter o histórico da conversa (thread_id)
    whatsapp_id = "5545999999999" 
    
    while True:
        try:
            # Obtém a entrada do usuário
            user_input = input("\nVocê: ").strip()
            
            # Verifica condições de saída
            if user_input.lower() in ["sair", "exit", "quit"]:
                print("Encerrando conversa...")
                break
                
            if not user_input:
                continue

            # Prepara o payload
            payload = {
                "message": user_input,
                "whatsapp_id": whatsapp_id
            }

            # Envia a requisição POST
            print("Enviando...", end="\r")
            response = requests.post(URL, json=payload, timeout=30)
            
            # Limpa a linha de "Enviando..."
            print(" " * 20, end="\r")

            if response.status_code == 200:
                data = response.json()
                agente_resposta = data.get('response', 'Resposta vazia')
                
                print(f"Agente: {agente_resposta}")
                
                # Exibe metadados se disponíveis (útil para debug)
                meta_info = []
                if data.get('nome_identificado'):
                    meta_info.append(f"Nome: {data['nome_identificado']}")
                if data.get('plano'):
                    meta_info.append(f"Plano: {data['plano']}")
                
                if meta_info:
                    print(f" [Info Extra: {', '.join(meta_info)}]")
            else:
                print(f"Erro do Servidor ({response.status_code}): {response.text}")

        except KeyboardInterrupt:
            print("\nEncerrando conversa...")
            break
        except requests.exceptions.ConnectionError:
            print("Erro de conexão: Não foi possível conectar ao servidor.")
        except Exception as e:
            print(f"Erro inesperado: {e}")

if __name__ == "__main__":
    main()
