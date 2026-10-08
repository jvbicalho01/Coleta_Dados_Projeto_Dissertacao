import pandas as pd

# ==========================================
# CONFIGURATION
# ==========================================
INPUT_FILE = 'repos_origin_language.csv'
OUTPUT_FILE = 'dataset_migrations.csv'

def filter_migrations():
    print(f"Loading data from {INPUT_FILE}...\n")
    
    # Read the dataset
    df = pd.read_csv(INPUT_FILE)
    initial_total = len(df)
    
    # === ECOSYSTEM UNIFICATION ===
    # Map TSX to TypeScript before counting or filtering
    df['origin_language'] = df['origin_language'].replace('TSX', 'TypeScript')
    
    # Values to discard from 'origin_language'
    # Includes native Rust projects, errors, and empty/unresolved entries
    ignored_values = [
        'Rust', 
        'Unknown / Empty', 
        'ERROR', 
        'Error', 
        'Tree Error'
    ]
    
    # Apply filters
    filtered_df = df[~df['origin_language'].isin(ignored_values)]
    filtered_df = filtered_df.dropna(subset=['origin_language'])
    
    final_total = len(filtered_df)
    discarded_total = initial_total - final_total
    
    # Summary report
    print("=== MIGRATION FILTER SUMMARY ===")
    print(f"Total repositories loaded: {initial_total}")
    print(f"Discarded (Native Rust or Errors): {discarded_total}")
    print(f"Real migrations identified: {final_total}")
    print("================================\n")
    
    if final_total > 0:
        print("🏆 TOP 10 ORIGIN LANGUAGES:")
        top_languages = filtered_df['origin_language'].value_counts().head(10)
        for lang, count in top_languages.items():
            print(f" - {lang}: {count} projects")
            
    # Overwrite/save the final migration dataset
    filtered_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Final dataset successfully saved to: '{OUTPUT_FILE}'")

if __name__ == "__main__":
    filter_migrations()