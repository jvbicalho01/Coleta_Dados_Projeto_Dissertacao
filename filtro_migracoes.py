import pandas as pd

# ==========================================
# CONFIGURAÇÕES
# ==========================================
# O arquivo gerado pelo seu script de coleta
ARQUIVO_ENTRADA = 'repos_origin_language.csv' 

# O seu dataset final, apenas com as migrações reais!
ARQUIVO_SAIDA = 'dataset_migrations.csv'

def filtrar_migracoes():
    print(f"Carregando os dados de {ARQUIVO_ENTRADA}...\n")
    
    # Lê o CSV
    df = pd.read_csv(ARQUIVO_ENTRADA)
    total_inicial = len(df)
    
    # Lista de valores que queremos descartar da coluna 'origin_language'
    # Inclui o próprio Rust e os casos de erro ou repositórios vazios.
    valores_ignorados = [
        'Rust', 
        'Unknown / Empty', 
        'ERROR', 
        'Error', 
        'Tree Error'
    ]
    
    # Aplica o filtro: 
    # 1. A linguagem de origem NÃO PODE estar na lista de ignorados
    # 2. A coluna de linguagem não pode estar vazia (NaN)
    df_filtrado = df[~df['origin_language'].isin(valores_ignorados)]
    df_filtrado = df_filtrado.dropna(subset=['origin_language'])
    
    total_final = len(df_filtrado)
    descartados = total_inicial - total_final
    
    # Exibe o resumo
    print("=== RESULTADO DO FILTRO DE MIGRAÇÕES ===")
    print(f"Total coletado: {total_inicial} repositórios")
    print(f"Descartados (Nasceram em Rust ou Erro): {descartados}")
    print(f"Migrações REAIS encontradas: {total_final} repositórios")
    print("========================================\n")
    
    if total_final > 0:
        print("🏆 TOP 10 LINGUAGENS DE ORIGEM:")
        # Conta a frequência de cada linguagem e mostra as 10 mais comuns
        top_linguagens = df_filtrado['origin_language'].value_counts().head(10)
        for ling, contagem in top_linguagens.items():
            print(f" - {ling}: {contagem} projetos")
            
    # Salva o novo dataset
    df_filtrado.to_csv(ARQUIVO_SAIDA, index=False)
    print(f"\n✅ Dataset final salvo com sucesso em: '{ARQUIVO_SAIDA}'")

if __name__ == "__main__":
    filtrar_migracoes()