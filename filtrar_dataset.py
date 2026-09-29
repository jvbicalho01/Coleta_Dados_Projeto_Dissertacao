import pandas as pd

def gerar_dataset_migracoes():
    # 1. Carrega o dataset tratado
    arquivo_entrada = 'repositorios_tratados.csv'
    arquivo_saida = 'dataset_migracoes_rust.csv'
    
    print(f"Carregando {arquivo_entrada}...")
    df = pd.read_csv(arquivo_entrada)
    total_bruto = len(df)

    # 2. Higienização: Remove os residuais (Desconhecida, Vazia, ERRO, None)
    df = df[~df['predominant_language_at_start'].astype(str).str.contains("ERRO|Vazia|Desconhecida|None", na=False, case=False)]
    
    # 3. Unificação de Ecossistemas (Importante para suas estatísticas)
    mapeamento_unificacao = {
        'TSX': 'TypeScript',
        'JSX': 'JavaScript',
        'Jupyter Notebook': 'Python',
        'C/C++ Header': 'C++',
        'GCC Machine Description': 'C'
    }
    df['predominant_language_at_start'] = df['predominant_language_at_start'].replace(mapeamento_unificacao)

    # 4. O FILTRO PRINCIPAL: Primeira linguagem diferente de Rust
    df_migrados = df[df['predominant_language_at_start'] != 'Rust']

    # (Opcional, mas seguro) Garante que a linguagem atual seja de fato Rust
    df_migrados = df_migrados[df_migrados['mainLanguage'] == 'Rust']

    # 5. Salva o resultado no CSV final
    df_migrados.to_csv(arquivo_saida, index=False, encoding='utf-8')

    # ==========================================
    # IMPRIME AS ESTATÍSTICAS PARA SUA DISSERTAÇÃO
    # ==========================================
    print("\n" + "="*50)
    print(" RESULTADOS FINAIS - MINERAÇÃO RIIR")
    print("="*50)
    print(f"Total de repositórios extraídos do SEART: {total_bruto}")
    print(f"Total válidos (com linguagem inicial identificada): {len(df)}")
    print(f"Total de repositórios que MIGRARAM para Rust: {len(df_migrados)}")
    print("="*50)
    
    if len(df_migrados) > 0:
        print("\nTOP 10 LINGUAGENS DE ORIGEM (De onde o Rust atraiu mais projetos?):")
        contagem = df_migrados['predominant_language_at_start'].value_counts().head(10)
        
        for linguagem, quantidade in contagem.items():
            porcentagem = (quantidade / len(df_migrados)) * 100
            print(f" -> {linguagem}: {quantidade} repositórios ({porcentagem:.1f}%)")
            
    print(f"\n✅ Dataset final salvo com sucesso em: '{arquivo_saida}'")

if __name__ == '__main__':
    gerar_dataset_migracoes()