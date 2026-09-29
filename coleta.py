import csv
import requests
import time
import os
import yaml
from collections import defaultdict
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# ==========================================
# CONFIGURAÇÕES
# ==========================================

# Insira aqui o seu Personal Access Token gerado no GitHub
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}'}

# Diretórios ignorados para não poluir a análise com dependências ou código autogerado
IGNORED_DIRS = {
    'vendor', 'node_modules', 'docs', 'build', 'dist', 
    'out', 'target', 'bin', 'obj', 'venv', '.venv', 'bower_components'
}

# ==========================================
# CARREGAMENTO DO LINGUIST
# ==========================================

def carregar_mapa_linguagens(caminho_yaml):
    print(f"Carregando heurísticas do {caminho_yaml}...")
    
    # 1. FORÇANDO EXCEÇÕES CONHECIDAS PARA EVITAR FALSOS POSITIVOS
    ext_map = {
        '.rs': 'Rust',           # Evita colisão com RenderScript
        '.md': 'IGNORE',         # Evita que README.md vire GCC Machine Description
        '.m': 'Objective-C',     # Evita colisão com MATLAB/Limbo
        '.ts': 'TypeScript'      # Evita colisão com arquivos de tradução XML
    }
    filename_map = {}
    
    try:
        with open(caminho_yaml, 'r', encoding='utf-8') as f:
            languages_data = yaml.safe_load(f)
            
        for lang_name, config in languages_data.items():
            lang_type = config.get('type', 'programming')
            if lang_type not in ['programming', 'markup']:
                continue
                
            for ext in config.get('extensions', []):
                ext_lower = ext.lower()
                # 2. Só mapeia se a extensão não for uma das nossas exceções forçadas
                if ext_lower not in ext_map:
                    ext_map[ext_lower] = lang_name
                    
            for filename in config.get('filenames', []):
                fn_lower = filename.lower()
                if fn_lower not in filename_map:
                    filename_map[fn_lower] = lang_name
                    
        print(f"Sucesso! {len(ext_map)} extensões e {len(filename_map)} arquivos mapeados.")
        return ext_map, filename_map
        
    except Exception as e:
        print(f"Erro ao carregar o arquivo YAML: {e}")
        return {}, {}

# ==========================================
# FUNÇÕES DE API
# ==========================================

def aguardar_rate_limit(headers):
    """Pausa a execução se o limite de requisições da API do GitHub for atingido."""
    remaining = int(headers.get('X-RateLimit-Remaining', 1))
    if remaining < 5:
        reset_time = int(headers.get('X-RateLimit-Reset', time.time() + 3600))
        sleep_time = max(0, reset_time - time.time()) + 5
        print(f"\n[!] Limite da API atingido. Aguardando {sleep_time:.0f} segundos para o reset...")
        time.sleep(sleep_time)

def obter_primeiro_commit(owner_repo):
    """Encontra o SHA do primeiro commit do repositório iterando pela paginação da API REST."""
    url = f"https://api.github.com/repos/{owner_repo}/commits"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        aguardar_rate_limit(resp.headers)
        
        if resp.status_code != 200:
            return None
            
        # Pega a última página (onde está o commit mais antigo)
        if 'Link' in resp.headers:
            links = resp.headers['Link'].split(',')
            last_url = None
            for link in links:
                if 'rel="last"' in link:
                    last_url = link[link.find('<')+1 : link.find('>')]
                    break
            
            if last_url:
                resp = requests.get(last_url, headers=HEADERS, timeout=15)
                aguardar_rate_limit(resp.headers)
        
        commits = resp.json()
        if not commits:
            return None
            
        # O último item da página mais antiga é o commit raiz
        return commits[-1]['sha']
        
    except Exception as e:
        print(f" Erro ao buscar commit de {owner_repo}: {e}")
        return None

def obter_linguagem_predominante(owner_repo, sha, ext_map, filename_map):
    """Busca a árvore de arquivos, ignora pastas irrelevantes e calcula a linguagem principal por bytes."""
    url = f"https://api.github.com/repos/{owner_repo}/git/trees/{sha}?recursive=1"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        aguardar_rate_limit(resp.headers)
        
        if resp.status_code != 200:
            return None
            
        tree = resp.json().get('tree', [])
        lang_sizes = defaultdict(int)
        
        for item in tree:
            if item['type'] == 'blob':
                path = item['path']
                partes_caminho = path.split('/')
                
                # Pula arquivos dentro de diretórios ignorados (ex: node_modules)
                if any(pasta in IGNORED_DIRS for pasta in partes_caminho):
                    continue
                
                size = item.get('size', 0)
                
                # Extrai apenas o nome final do arquivo para análise
                nome_arquivo = os.path.basename(path)
                _, ext = os.path.splitext(nome_arquivo)
                
                lang = None
                
                # 1. Tenta casar o nome exato (prioridade para arquivos como Makefile)
                if nome_arquivo.lower() in filename_map:
                    lang = filename_map[nome_arquivo.lower()]
                # 2. Se não encontrou, tenta casar pela extensão do arquivo
                elif ext.lower() in ext_map:
                    lang = ext_map[ext.lower()]
                    
                if lang and lang != 'IGNORE':
                    lang_sizes[lang] += size
                    
        if not lang_sizes:
            return "Desconhecida / Vazia (após filtros)"
            
        # Retorna a linguagem com maior volume de bytes no commit
        return max(lang_sizes, key=lang_sizes.get)
        
    except Exception as e:
        print(f" Erro ao analisar árvore de {owner_repo}: {e}")
        return None

# ==========================================
# PROCESSAMENTO DE DADOS
# ==========================================

def processar_dataset(csv_entrada, csv_saida, ext_map, filename_map):
    # 1. Mapeia o que já foi processado para não fazer de novo
    repos_processados = set()
    if os.path.exists(csv_saida):
        with open(csv_saida, mode='r', encoding='utf-8') as f_out_read:
            reader = csv.DictReader(f_out_read)
            repo_column_out = 'name' if 'name' in reader.fieldnames else 'repo'
            for row in reader:
                repos_processados.add(row[repo_column_out])
        print(f"Retomando a execução: {len(repos_processados)} repositórios já processados encontrados.")

    # 2. Abre o arquivo de entrada para leitura e o de saída no modo 'append' (anexar)
    with open(csv_entrada, mode='r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        repo_column = 'name' if 'name' in reader.fieldnames else 'repo'
        
        # Determina se precisa escrever o cabeçalho
        escrever_cabecalho = not os.path.exists(csv_saida) or os.path.getsize(csv_saida) == 0
        
        with open(csv_saida, mode='a', newline='', encoding='utf-8') as f_out:
            fieldnames = reader.fieldnames + ['first_commit_sha', 'predominant_language_at_start']
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            
            if escrever_cabecalho:
                writer.writeheader()
            
            for idx, row in enumerate(reader, 1):
                owner_repo = row[repo_column]
                
                # Se já estiver no CSV de saída, apenas pula
                if owner_repo in repos_processados:
                    continue
                    
                print(f"[{idx}/~60000] Analisando: {owner_repo}...", end=" ", flush=True)
                
                sha = obter_primeiro_commit(owner_repo)
                
                if sha:
                    lang = obter_linguagem_predominante(owner_repo, sha, ext_map, filename_map)
                    row['first_commit_sha'] = sha
                    row['predominant_language_at_start'] = lang
                    print(f"[{lang}]")
                else:
                    row['first_commit_sha'] = "ERRO/VAZIO"
                    row['predominant_language_at_start'] = "ERRO"
                    print("[ERRO AO BUSCAR]")
                    
                writer.writerow(row)

# ==========================================
# EXECUÇÃO PRINCIPAL
# ==========================================

if __name__ == '__main__':
    # Nomes dos arquivos no diretório atual
    ARQUIVO_SEART = 'rust_repositories.csv'
    ARQUIVO_RESULTADO = 'repositorios_analisados.csv'
    ARQUIVO_YAML = 'languages.yml' 
    
    if GITHUB_TOKEN == 'SEU_TOKEN_AQUI':
        print("Aviso: Insira seu GITHUB_TOKEN nas configurações do script antes de executar.")
    elif not os.path.exists(ARQUIVO_YAML):
        print(f"Erro: O arquivo '{ARQUIVO_YAML}' não foi encontrado.")
        print("Baixe-o via terminal com:")
        print("wget https://raw.githubusercontent.com/github-linguist/linguist/master/lib/linguist/languages.yml")
    elif not os.path.exists(ARQUIVO_SEART):
        print(f"Erro: O arquivo '{ARQUIVO_SEART}' não foi encontrado.")
    else:
        mapa_extensoes, mapa_arquivos = carregar_mapa_linguagens(ARQUIVO_YAML)
        
        if mapa_extensoes or mapa_arquivos:
            print("Iniciando extração do histórico dos repositórios...")
            processar_dataset(ARQUIVO_SEART, ARQUIVO_RESULTADO, mapa_extensoes, mapa_arquivos)
            print("\nDataset gerado com sucesso!")