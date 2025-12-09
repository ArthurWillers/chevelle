import sys
from .app import ChevelleApp  # Importa a classe do arquivo app.py vizinho

def main():
    """Função que inicia o programa."""
    # 1. Cria a aplicação
    app = ChevelleApp()

    # 2. Roda a aplicação e devolve o código de saída para o sistema
    sys.exit(app.run())


if __name__ == "__main__":
    main()