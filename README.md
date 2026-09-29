# Mineração de Dados: Fenômeno "Rewrite It In Rust" (RIIR) 🦀

Este repositório contém os *scripts* de coleta, tratamento e filtragem de dados desenvolvidos para a minha dissertação de Mestrado no Departamento de Ciência da Computação (DCC) da Universidade Federal de Minas Gerais (UFMG).

O objetivo deste pipeline é extrair e higienizar um *dataset* de repositórios de código aberto que originalmente nasceram em outras linguagens de programação e migraram para **Rust**. Esse conjunto de dados servirá como base empírica para testes de tradução de código e transplante de bibliotecas utilizando *Large Language Models* (LLMs).

## ⚙️ Arquitetura do Pipeline

A metodologia de extração foi dividida em três etapas sequenciais, desenhadas para minimizar o uso de rede (abordagem *zero-clone*) e respeitar os limites de taxa (*rate limits*) da API do GitHub:

1. **`coleta.py` (Extração Inicial):** 
   Lê um *dataset* bruto pré-filtrado via [SEART GitHub Search](https://seart-ghs.si.usi.ch/) (projetos com Rust como linguagem atual). Utiliza a *Git Trees API* para simular o *GitHub Linguist* e identificar a linguagem predominante no exato momento do **primeiro commit** do projeto.

2. **`tratamento.py` (Fast-Forwarding):** 
   Resolve a anomalia de repositórios inicializados via interface web (apenas com `README.md` ou `.gitignore`). O script itera sobre o histórico dos repositórios "desconhecidos" até os 10 primeiros commits, buscando a primeira introdução de código estrutural mensurável.

3. **`filtar_dataset.py` (Análise e Filtragem):** 
   Utiliza a biblioteca `pandas` para higienizar os dados finais, unificar ecossistemas (ex: TSX e JavaScript) e isolar estritamente os repositórios cuja linguagem original é diferente de Rust, gerando as estatísticas finais do fenômeno RIIR.

## 🚀 Como configurar e executar

### 1. Pré-requisitos
Certifique-se de ter o Python 3 instalado e instale as dependências necessárias:
```bash
pip install requests pandas python-dotenv pyyaml
```

### 2. Configuração de Credenciais
Para se comunicar com a API do GitHub, você precisa de um *Personal Access Token* (PAT).
Crie um arquivo chamado `.env` na raiz do projeto e insira o seu token:
```text
GITHUB_TOKEN=ghp_seu_token_gerado_no_github_aqui
```
> **Nota:** O arquivo `.env` já está no `.gitignore` por segurança e nunca deve ser enviado (commitado) para o repositório.

### 3. Ordem de Execução
Os *scripts* devem ser executados na seguinte ordem, aguardando a finalização completa de cada um:

```bash
# 1. Identifica a linguagem inicial dos repositórios base
python3 coleta.py

# 2. Executa a repescagem (Fast-Forwarding) nos repositórios vazios
python3 tratamento.py

# 3. Limpa, unifica e filtra apenas as migrações reais para Rust
python3 filtrar_dataset.py
```
