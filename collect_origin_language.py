import csv
import requests
import time
import os
import yaml
import re
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==========================================
# CONFIGURATION
# ==========================================
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# Input file from the 1000-star filter
INPUT_FILE = 'repos_rust_1000_stars.csv'
OUTPUT_FILE = 'repos_origin_language.csv'
YAML_FILE = 'languages.yml'

# Directories ignored to avoid skewing code volume analysis
IGNORED_DIRS = {
    'vendor', 'node_modules', 'docs', 'build', 'dist', 
    'out', 'target', 'bin', 'obj', 'venv', '.venv', 'bower_components'
}

# ==========================================
# LINGUIST RULES LOADING
# ==========================================
def load_language_map(yaml_path):
    """Parses Linguist languages.yml to build extension and filename mappings."""
    print(f"Loading heuristics from {yaml_path}...")
    ext_map = {
        '.rs': 'Rust', '.md': 'IGNORE', '.m': 'Objective-C', '.ts': 'TypeScript'
    }
    filename_map = {}
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
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
                    
        print(f"Success! {len(ext_map)} extensions and {len(filename_map)} filenames mapped.\n")
        return ext_map, filename_map
        
    except Exception as e:
        print(f"Error loading YAML file: {e}")
        return {}, {}

# ==========================================
# API UTILITIES & RATE LIMITING
# ==========================================
def wait_for_rate_limit(headers):
    """Pauses execution if GitHub API rate limit threshold is reached."""
    remaining = int(headers.get('X-RateLimit-Remaining', 1))
    if remaining < 5:
        reset_time = int(headers.get('X-RateLimit-Reset', time.time() + 3600))
        sleep_time = max(0, reset_time - time.time()) + 5
        print(f"\n[!] API rate limit reached. Waiting {sleep_time:.0f} seconds for reset...")
        time.sleep(sleep_time)

def get_last_page(url):
    """Determines the last available page number via GitHub Link headers."""
    response = requests.get(url, headers=HEADERS, timeout=15)
    wait_for_rate_limit(response.headers)
    
    if response.status_code != 200:
        return 0
    
    link_header = response.headers.get('Link', '')
    match = re.search(r'page=(\d+)>; rel="last"', link_header)
    if match:
        return int(match.group(1))
    return 1

# ==========================================
# MATURITY DETECTION & LANGUAGE EXTRACTION
# ==========================================
def get_target_sha(owner_repo, total_commits_csv, total_releases_csv):
    """Retrieves target SHA via 1st Release or falls back to the 10% commit checkpoint."""
    try:
        if total_releases_csv > 0:
            url_releases = f'https://api.github.com/repos/{owner_repo}/releases?per_page=1'
            total_releases = get_last_page(url_releases)
            
            if total_releases > 0:
                first_release_resp = requests.get(f'{url_releases}&page={total_releases}', headers=HEADERS, timeout=15)
                wait_for_rate_limit(first_release_resp.headers)
                if first_release_resp.status_code == 200:
                    release_data = first_release_resp.json()
                    if release_data:
                        return release_data[0]['tag_name'], "First Release"

        if total_commits_csv > 0:
            ten_percent_commit = max(1, int(total_commits_csv * 0.1))
            target_page = total_commits_csv - ten_percent_commit + 1
            
            target_commit_url = f'https://api.github.com/repos/{owner_repo}/commits?per_page=1&page={target_page}'
            commit_resp = requests.get(target_commit_url, headers=HEADERS, timeout=15)
            wait_for_rate_limit(commit_resp.headers)
            
            if commit_resp.status_code == 200:
                commit_data = commit_resp.json()
                if commit_data:
                    return commit_data[0]['sha'], f"10% Commit ({ten_percent_commit}/{total_commits_csv})"
            elif commit_resp.status_code == 422:
                return None, "Error: Commits mismatch with CSV"
                    
        return None, "Empty / Failed"
    except Exception as e:
        print(f" Error fetching SHA for {owner_repo}: {e}")
        return None, "Error"

def get_predominant_language(owner_repo, sha, ext_map, filename_map):
    """Analyzes the Git tree at the exact target SHA to extract byte volume per language."""
    url = f"https://api.github.com/repos/{owner_repo}/git/trees/{sha}?recursive=1"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        wait_for_rate_limit(resp.headers)
        
        if resp.status_code != 200:
            return "Tree Error"
            
        tree = resp.json().get('tree', [])
        lang_sizes = defaultdict(int)
        
        for item in tree:
            if item['type'] == 'blob':
                path = item['path']
                path_parts = path.split('/')
                
                if any(folder in IGNORED_DIRS for folder in path_parts):
                    continue
                
                size = item.get('size', 0)
                filename = os.path.basename(path)
                _, ext = os.path.splitext(filename)
                
                lang = None
                if filename.lower() in filename_map:
                    lang = filename_map[filename.lower()]
                elif ext.lower() in ext_map:
                    lang = ext_map[ext.lower()]
                    
                if lang and lang != 'IGNORE':
                    lang_sizes[lang] += size
                    
        if not lang_sizes:
            return "Unknown / Empty"
            
        return max(lang_sizes, key=lang_sizes.get)
        
    except Exception as e:
        print(f" Error parsing tree for {owner_repo}: {e}")
        return "Error"

# ==========================================
# PROCESSING PIPELINE & RESUME HANDLER
# ==========================================
def process_dataset(csv_input, csv_output, ext_map, filename_map):
    processed_repos = set()
    
    if os.path.exists(csv_output):
        with open(csv_output, mode='r', encoding='utf-8') as f_out_read:
            reader = csv.DictReader(f_out_read)
            repo_column_out = 'name' if 'name' in reader.fieldnames else 'repo'
            for row in reader:
                processed_repos.add(row[repo_column_out])
        print(f"Resuming: {len(processed_repos)} already processed repositories found.")

    with open(csv_input, mode='r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        repo_column = 'name' if 'name' in reader.fieldnames else 'repo'
        
        write_header = not os.path.exists(csv_output) or os.path.getsize(csv_output) == 0
        
        with open(csv_output, mode='a', newline='', encoding='utf-8') as f_out:
            fieldnames = reader.fieldnames + ['target_sha', 'discovery_method', 'origin_language']
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            
            if write_header:
                writer.writeheader()
            
            for idx, row in enumerate(reader, 1):
                owner_repo = row[repo_column]
                
                if owner_repo in processed_repos:
                    continue
                    
                print(f"[{idx}] Analyzing: {owner_repo}...", end=" ", flush=True)
                
                try:
                    total_commits_csv = int(float(row.get('commits', 0)))
                except (ValueError, TypeError):
                    total_commits_csv = 0
                    
                try:
                    total_releases_csv = int(float(row.get('releases', 0)))
                except (ValueError, TypeError):
                    total_releases_csv = 0
                
                sha, method = get_target_sha(owner_repo, total_commits_csv, total_releases_csv)
                
                if sha:
                    lang = get_predominant_language(owner_repo, sha, ext_map, filename_map)
                    row['target_sha'] = sha
                    row['discovery_method'] = method
                    row['origin_language'] = lang
                    print(f"[{lang}] via {method}")
                else:
                    row['target_sha'] = "ERROR"
                    row['discovery_method'] = method
                    row['origin_language'] = "ERROR"
                    print("[FAILED]")
                    
                writer.writerow(row)

if __name__ == '__main__':
    if not GITHUB_TOKEN or GITHUB_TOKEN == 'SEU_TOKEN_AQUI':
        print("Warning: Configure your .env file with a valid GITHUB_TOKEN.")
    elif not os.path.exists(YAML_FILE):
        print(f"Error: File '{YAML_FILE}' was not found.")
    elif not os.path.exists(INPUT_FILE):
        print(f"Error: File '{INPUT_FILE}' was not found.")
    else:
        ext_map, filename_map = load_language_map(YAML_FILE)
        if ext_map or filename_map:
            print("Starting maturity-based history extraction...")
            process_dataset(INPUT_FILE, OUTPUT_FILE, ext_map, filename_map)
            print("\nDataset generated successfully!")