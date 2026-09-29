import requests
import time
import csv
import os
import yaml
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# ==========================================
# CONFIGURAÇÕES
# ==========================================
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
ARQUIVO_ENTRADA = 'repositorios_analisados.csv'
ARQUIVO_SAIDA = 'repositorios_tratados.csv'

HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

MAX_TENTATIVAS_COMMITS = 10 # Testa até os 10 primeiros commits
TIMEOUT = 15 # Evita o travamento (hang) da rede

# ==========================================
# FUNÇÕES DE API E RATE LIMIT (Reaproveitadas)
# ==========================================
def aguardar_rate_limit(response):
    if 'X-RateLimit-Remaining' in response.headers:
        remaining = int(response.headers['X-RateLimit-Remaining'])
        if remaining < 5:
            reset_time = int(response.headers['X-RateLimit-Reset'])
            agora = int(time.time())
            espera = max(0, reset_time - agora) + 5
            print(f"\n[!] Limite da API atingido. Aguardando {espera} segundos para o reset...")
            time.sleep(espera)

def carregar_mapa_linguagens(caminho_yaml='languages.yml'):
    ext_map = {
        '.rs': 'Rust', '.md': 'IGNORE', '.m': 'Objective-C', '.ts': 'TypeScript'
    }
    filename_map = {}
    try:
        with open(caminho_yaml, 'r', encoding='utf-8') as f:
            languages_data = yaml.safe_load(f)
        for lang_name, config in languages_data.items():
            if config.get('type', 'programming') not in ['programming', 'markup']:
                continue
            for ext in config.get('extensions', []):
                if ext.lower() not in ext_map:
                    ext_map[ext.lower()] = lang_name
            for filename in config.get('filenames', []):
                if filename.lower() not in filename_map:
                    filename_map[filename.lower()] = lang_name
        return ext_map, filename_map
    except Exception as e:
        print(f"Erro ao carregar YAML: {e}")
        return {}, {}

def testar_arvore_commit(owner_repo, sha, ext_map, filename_map):
    """Testa se a árvore de um commit específico possui linguagens de programação."""
    url = f"https://api.github.com/repos/{owner_repo}/git/trees/{sha}?recursive=1"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        aguardar_rate_limit(response)
        
        if response.status_code != 200:
            return None
            
        tree = response.json().get('tree', [])
        lang_sizes = {}
        
        for item in tree:
            if item['type'] == 'blob':
                path = item['path']
                # Ignora pastas de dependências
                if any(ignored in path.split('/') for ignored in ['vendor', 'node_modules', 'dist', 'build']):
                    continue
                    
                size = item.get('size', 0)
                filename = os.path.basename(path).lower()
                _, ext = os.path.splitext(filename)
                
                lang = None
                if filename in filename_map:
                    lang = filename_map[filename]
                elif ext.lower() in ext_map:
                    lang = ext_map[ext.lower()]
                    
                if lang and lang != 'IGNORE':
                    lang_sizes[lang] = lang_sizes.get(lang, 0) + size
                    
        if not lang_sizes:
            return "Vazia" # Ainda não tem código
            
        # Retorna a linguagem com mais bytes naquele commit
        return max(lang_sizes, key=lang_sizes.get)
        
    except requests.exceptions.RequestException:
        return "ERRO"

def obter_commit_com_codigo(owner_repo, ext_map, filename_map):
    """Avança cronologicamente nos commits até achar código válido."""
    url = f"https://api.github.com/repos/{owner_repo}/commits?per_page=30"
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        aguardar_rate_limit(response)
        
        if response.status_code != 200:
            return "ERRO/NAO_ENCONTRADO", "ERRO"
            
        # Lógica para pegar os commits mais antigos (última página)
        if 'Link' in response.headers:
            links = response.headers['Link']
            last_url = None
            for link in links.split(','):
                if 'rel="last"' in link:
                    last_url = link[link.find("<")+1 : link.find(">")]
            
            if last_url:
                response = requests.get(last_url, headers=HEADERS, timeout=TIMEOUT)
                aguardar_rate_limit(response)
                
        commits = response.json()
        
        # A API retorna do mais novo pro mais velho. Nós invertemos para ficar cronológico.
        commits_antigos = list(reversed(commits))
        
        # Fast-Forwarding: testa um por um até o limite
        for i, commit_data in enumerate(commits_antigos[:MAX_TENTATIVAS_COMMITS]):
            sha = commit_data['sha']
            linguagem = testar_arvore_commit(owner_repo, sha, ext_map, filename_map)
            
            if linguagem not in ["Vazia", "ERRO", None]:
                # Achou o código real!
                return sha, linguagem
                
        return "ERRO_LIMITE_TENTATIVAS", "Desconhecida / Vazia (após filtros)"
        
    except requests.exceptions.RequestException:
        return "ERRO_REDE", "ERRO"

# ==========================================
# EXECUÇÃO PRINCIPAL
# ==========================================
def executar_tratamento():
    ext_map, filename_map = carregar_mapa_linguagens()
    
    # Termos que identificam repositórios que precisam de tratamento
    termos_invalidos = ["Vazia", "Desconhecida", "ERRO", "None"]
    
    with open(ARQUIVO_ENTRADA, mode='r', encoding='utf-8') as f_in, \
         open(ARQUIVO_SAIDA, mode='w', newline='', encoding='utf-8') as f_out:
             
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
        writer.writeheader()
        
        for idx, row in enumerate(reader, 1):
            owner_repo = row.get('name', row.get('repo'))
            lang_atual = str(row.get('predominant_language_at_start', ''))
            
            # Se for um repositório inválido/vazio, faz o Fast-Forward
            if any(termo in lang_atual for termo in termos_invalidos):
                print(f"[{idx}] Tratando: {owner_repo}...", end=" ", flush=True)
                
                novo_sha, nova_lang = obter_commit_com_codigo(owner_repo, ext_map, filename_map)
                
                row['first_commit_sha'] = novo_sha
                row['predominant_language_at_start'] = nova_lang
                print(f"[{nova_lang}]")
            
            # Escreve a linha (corrigida ou original) no novo arquivo
            writer.writerow(row)
            
    print(f"\n✅ Tratamento concluído! Dataset refinado salvo em: {ARQUIVO_SAIDA}")

if __name__ == '__main__':
    if GITHUB_TOKEN == 'SEU_TOKEN_AQUI':
         print("Aviso: Insira seu GITHUB_TOKEN.")
    else:
         executar_tratamento()