import pandas as pd

# ==========================================
# CONFIGURAÇÕES
# ==========================================
# O arquivo CSV gigante que você baixou direto do site do SEART
ARQUIVO_BRUTO_SEART = 'results_seart_0610.csv' 

# O novo arquivo que será a entrada do seu script coleta.py
ARQUIVO_BASE_COLETA = 'repos_base_1000_estrelas.csv'

def aplicar_filtro_estrelas():
    print("Carregando o dataset bruto do SEART...")
    
    # O SEART costuma separar as colunas por vírgula, mas dependendo de 
    # como você baixou, pode ser ponto e vírgula.
    df = pd.read_csv(ARQUIVO_BRUTO_SEART)
    total_antes = len(df)
    
    # ATENÇÃO: Verifique o nome da coluna no seu CSV. 
    # O SEART normalmente chama a coluna de estrelas de 'stargazers' ou 'stars'
    coluna_estrelas = 'stargazers' 
    
    # Aplica o filtro de repositórios com 1000 estrelas ou mais
    df_filtrado = df[df[coluna_estrelas] >= 1000]
    
    total_depois = len(df_filtrado)
    descartados = total_antes - total_depois
    
    print("\n=== RESULTADOS DO FILTRO DE ESTRELAS ===")
    print(f"Total bruto do SEART: {total_antes} repositórios")
    print(f"Total Relevantes (>= 1000 estrelas): {total_depois} repositórios")
    print(f"Repositórios pequenos descartados: {descartados}")
    print("========================================\n")
    
    # Salva o novo arquivo
    df_filtrado.to_csv(ARQUIVO_BASE_COLETA, index=False)
    print(f"✅ Novo dataset salvo! Use o arquivo '{ARQUIVO_BASE_COLETA}' no seu script coleta.py.")

if __name__ == "__main__":
    aplicar_filtro_estrelas()