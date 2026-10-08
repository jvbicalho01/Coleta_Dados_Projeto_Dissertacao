import pandas as pd

# ==========================================
# CONFIGURATION
# ==========================================
# Raw CSV file downloaded directly from SEART
RAW_SEART_FILE = 'results_seart_0610.csv'

# Output file that serves as input for the maturity collection script
OUTPUT_FILE = 'repos_rust_1000_stars.csv'

def apply_star_filter():
    print(f"Loading raw SEART dataset from {RAW_SEART_FILE}...")
    
    # SEART typically uses commas, but verify delimiter if an error occurs
    df = pd.read_csv(RAW_SEART_FILE)
    total_before = len(df)
    
    # Column verification: SEART typically names this column 'stargazers' or 'stars'
    star_column = 'stargazers'
    
    # Filter repositories with 1000 or more stars
    filtered_df = df[df[star_column] >= 1000]
    
    total_after = len(filtered_df)
    discarded_total = total_before - total_after
    
    print("\n=== STAR FILTER SUMMARY ===")
    print(f"Total raw SEART repositories: {total_before}")
    print(f"Relevant repositories (>= 1000 stars): {total_after}")
    print(f"Small repositories discarded: {discarded_total}")
    print("===========================\n")
    
    # Save the filtered dataset
    filtered_df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Filtered dataset saved successfully to: '{OUTPUT_FILE}'")

if __name__ == "__main__":
    apply_star_filter()