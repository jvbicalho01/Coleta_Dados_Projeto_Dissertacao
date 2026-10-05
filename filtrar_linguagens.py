import pandas as pd

# ==========================================
# CONFIGURAÇÕES
# ==========================================
# Nome do arquivo gerado no seu filtro anterior
ARQUIVO_ENTRADA = 'dataset_migracoes_rust.csv' 
# Nome do novo arquivo que será gerado agora
ARQUIVO_SAIDA = 'dataset_linguagens_stackoverflow.csv'

linguagens_relevantes = [
    'Python', 'HTML', 'CSS', 'JavaScript', 'TypeScript', 
    'Go', 'C#', 'C++', 'Java', 'C', 'Kotlin', 'PHP', 
    'Zig', 'Lua', 'Swift', 'Elixir', 'Dart', 'Ruby', 'OCaml'
]

def aplicar_filtro():
    print("Carregando o dataset...")
    # Lê o arquivo CSV
    df = pd.read_csv(ARQUIVO_ENTRADA)
    total_antes = len(df)
    
    # Converte a lista permitida para minúsculas para evitar problemas (ex: JavaScript vs javascript)
    linguagens_permitidas_lower = [lang.lower() for lang in linguagens_relevantes]
    
    coluna_linguagem = 'predominant_language_at_start' 
    
    # Aplica o filtro
    df_filtrado = df[df[coluna_linguagem].str.lower().isin(linguagens_permitidas_lower)]
    
    total_depois = len(df_filtrado)
    descartados = total_antes - total_depois
    
    print("\n=== RESULTADOS DO FILTRO ===")
    print(f"Total antes do filtro: {total_antes}")
    print(f"Total depois do filtro: {total_depois}")
    print(f"Projetos descartados (Nix, Shell, Makefile, etc): {descartados}")
    print("============================\n")
    
    # Salva o resultado em um novo arquivo
    df_filtrado.to_csv(ARQUIVO_SAIDA, index=False)
    print(f"✅ Novo dataset salvo com sucesso em: {ARQUIVO_SAIDA}")

if __name__ == "__main__":
    aplicar_filtro()