import csv
import requests
import time
import os
import yaml
import re
from collections import defaultdict
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# ==========================================
# CONFIGURAÇÕES
# ==========================================
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# Arquivo gerado pelo seu filtro de 1000 estrelas
ARQUIVO_ENTRADA = 'repos_rust_1000_stars.csv'
ARQUIVO_SAIDA = 'repos_origin_language.csv'
ARQUIVO_YAML = 'languages.yml'

# Diretórios ignorados para não poluir a análise
IGNORED_DIRS = {
    'vendor', 'node_modules', 'docs', 'build', 'dist', 
    'out', 'target', 'bin', 'obj', 'venv', '.venv', 'bower_components'
}

# ==========================================
# CARREGAMENTO DO LINGUIST
# ==========================================
def carregar_mapa_linguagens(caminho_yaml):
    print(f"Carregando heurísticas do {caminho_yaml}...")
    ext_map = {
        '.rs': 'Rust', '.md': 'IGNORE', '.m': 'Objective-C', '.ts': 'TypeScript'
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
                if ext_lower not in ext_map:
                    ext_map[ext_lower] = lang_name
                    
            for filename in config.get('filenames', []):
                fn_lower = filename.lower()
                if fn_lower not in filename_map:
                    filename_map[fn_lower] = lang_name
                    
        print(f"Sucesso! {len(ext_map)} extensões e {len(filename_map)} arquivos mapeados.\n")
        return ext_map, filename_map
        
    except Exception as e:
        print(f"Erro ao carregar o arquivo YAML: {e}")
        return {}, {}

# ==========================================
# FUNÇÕES DE API E RATE LIMIT
# ==========================================
def aguardar_rate_limit(headers):
    """Pausa a execução se o limite de requisições da API do GitHub for atingido."""
    remaining = int(headers.get('X-RateLimit-Remaining', 1))
    if remaining < 5:
        reset_time = int(headers.get('X-RateLimit-Reset', time.time() + 3600))
        sleep_time = max(0, reset_time - time.time()) + 5
        print(f"\n[!] Limite da API atingido. Aguardando {sleep_time:.0f} segundos para o reset...")
        time.sleep(sleep_time)

def obter_ultima_pagina(url):
    """Descobre o total de páginas lendo o cabeçalho 'Link'."""
    response = requests.get(url, headers=HEADERS, timeout=15)
    aguardar_rate_limit(response.headers)
    
    if response.status_code != 200:
        return 0
    
    link_header = response.headers.get('Link', '')
    match = re.search(r'page=(\d+)>; rel="last"', link_header)
    if match:
        return int(match.group(1))
    return 1

# ==========================================
# DESCOBERTA DA MATURIDADE E LINGUAGEM
# ==========================================
def obter_sha_alvo(owner_repo, total_commits_csv, total_releases_csv):
    """Tenta encontrar a 1ª Release; se não houver, calcula os 10% direto com o valor do CSV."""
    try:
        if total_releases_csv > 0:
            url_releases = f'https://api.github.com/repos/{owner_repo}/releases?per_page=1'
            total_releases = obter_ultima_pagina(url_releases)
            
            if total_releases > 0:
                resp_primeira_release = requests.get(f'{url_releases}&page={total_releases}', headers=HEADERS, timeout=15)
                aguardar_rate_limit(resp_primeira_release.headers)
                if resp_primeira_release.status_code == 200:
                    dados_release = resp_primeira_release.json()
                    if dados_release:
                        # TRADUZIDO: "Primeira Release" -> "First Release"
                        return dados_release[0]['tag_name'], "First Release"

        if total_commits_csv > 0:
            commit_dez_porcento = max(1, int(total_commits_csv * 0.1))
            pagina_alvo = total_commits_csv - commit_dez_porcento + 1
            
            url_commit_alvo = f'https://api.github.com/repos/{owner_repo}/commits?per_page=1&page={pagina_alvo}'
            resp_commit = requests.get(url_commit_alvo, headers=HEADERS, timeout=15)
            aguardar_rate_limit(resp_commit.headers)
            
            if resp_commit.status_code == 200:
                dados_commit = resp_commit.json()
                if dados_commit:
                    # TRADUZIDO: Formato do commit
                    return dados_commit[0]['sha'], f"10% Commit ({commit_dez_porcento}/{total_commits_csv})"
            elif resp_commit.status_code == 422:
                return None, "Error: Commits mismatch with CSV"
                    
        return None, "Empty / Failed"
    except Exception as e:
        print(f" Erro ao buscar SHA de {owner_repo}: {e}")
        return None, "Error"

def obter_linguagem_predominante(owner_repo, sha, ext_map, filename_map):
    """Analisa a árvore de arquivos no exato milissegundo do SHA alvo."""
    url = f"https://api.github.com/repos/{owner_repo}/git/trees/{sha}?recursive=1"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        aguardar_rate_limit(resp.headers)
        
        if resp.status_code != 200:
            return "Tree Error"
            
        tree = resp.json().get('tree', [])
        lang_sizes = defaultdict(int)
        
        for item in tree:
            if item['type'] == 'blob':
                path = item['path']
                partes_caminho = path.split('/')
                
                if any(pasta in IGNORED_DIRS for pasta in partes_caminho):
                    continue
                
                size = item.get('size', 0)
                nome_arquivo = os.path.basename(path)
                _, ext = os.path.splitext(nome_arquivo)
                
                lang = None
                if nome_arquivo.lower() in filename_map:
                    lang = filename_map[nome_arquivo.lower()]
                elif ext.lower() in ext_map:
                    lang = ext_map[ext.lower()]
                    
                if lang and lang != 'IGNORE':
                    lang_sizes[lang] += size
                    
        if not lang_sizes:
            return "Unknown / Empty"
            
        return max(lang_sizes, key=lang_sizes.get)
        
    except Exception as e:
        print(f" Erro na árvore de {owner_repo}: {e}")
        return "Error"

# ==========================================
# EXECUÇÃO E CONTROLE DE RETOMADA
# ==========================================
def processar_dataset(csv_entrada, csv_saida, ext_map, filename_map):
    repos_processados = set()
    
    if os.path.exists(csv_saida):
        with open(csv_saida, mode='r', encoding='utf-8') as f_out_read:
            reader = csv.DictReader(f_out_read)
            repo_column_out = 'name' if 'name' in reader.fieldnames else 'repo'
            for row in reader:
                repos_processados.add(row[repo_column_out])
        print(f"Retomando: {len(repos_processados)} repositórios já processados encontrados.")

    with open(csv_entrada, mode='r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        repo_column = 'name' if 'name' in reader.fieldnames else 'repo'
        
        escrever_cabecalho = not os.path.exists(csv_saida) or os.path.getsize(csv_saida) == 0
        
        with open(csv_saida, mode='a', newline='', encoding='utf-8') as f_out:
            # TRADUZIDO: Nomes das colunas
            fieldnames = reader.fieldnames + ['target_sha', 'discovery_method', 'origin_language']
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            
            if escrever_cabecalho:
                writer.writeheader()
            
            for idx, row in enumerate(reader, 1):
                owner_repo = row[repo_column]
                
                if owner_repo in repos_processados:
                    continue
                    
                print(f"[{idx}] Analisando: {owner_repo}...", end=" ", flush=True)
                
                try:
                    total_commits_csv = int(float(row.get('commits', 0)))
                except (ValueError, TypeError):
                    total_commits_csv = 0
                    
                try:
                    total_releases_csv = int(float(row.get('releases', 0)))
                except (ValueError, TypeError):
                    total_releases_csv = 0
                
                sha, metodo = obter_sha_alvo(owner_repo, total_commits_csv, total_releases_csv)
                
                if sha:
                    lang = obter_linguagem_predominante(owner_repo, sha, ext_map, filename_map)
                    row['target_sha'] = sha
                    row['discovery_method'] = metodo
                    row['origin_language'] = lang
                    print(f"[{lang}] via {metodo}")
                else:
                    row['target_sha'] = "ERROR"
                    row['discovery_method'] = metodo
                    row['origin_language'] = "ERROR"
                    print("[FALHA]")
                    
                writer.writerow(row)

if __name__ == '__main__':
    if not GITHUB_TOKEN or GITHUB_TOKEN == 'SEU_TOKEN_AQUI':
        print("Aviso: Configure o arquivo .env com o seu GITHUB_TOKEN.")
    elif not os.path.exists(ARQUIVO_YAML):
        print(f"Erro: O arquivo '{ARQUIVO_YAML}' não foi encontrado.")
    elif not os.path.exists(ARQUIVO_ENTRADA):
        print(f"Erro: O arquivo '{ARQUIVO_ENTRADA}' não foi encontrado.")
    else:
        mapa_extensoes, mapa_arquivos = carregar_mapa_linguagens(ARQUIVO_YAML)
        if mapa_extensoes or mapa_arquivos:
            print("Iniciando extração do histórico baseada em maturidade...")
            processar_dataset(ARQUIVO_ENTRADA, ARQUIVO_SAIDA, mapa_extensoes, mapa_arquivos)
            print("\nDataset gerado com sucesso!")