import pandas as pd

try:
    # Try reading with different encodings
    for encoding in ['utf-8', 'latin1', 'cp1252', 'utf-16']:
        try:
            print(f"Trying encoding: {encoding}")
            df = pd.read_csv('knowledge_base.csv', encoding=encoding, nrows=5)
            print("Success! First 5 rows:")
            print(df.head())
            print("\nColumns:", df.columns.tolist())
            print("\nFirst row as dict:", df.iloc[0].to_dict())
            break
        except Exception as e:
            print(f"Failed with {encoding}: {str(e)[:100]}...")
            continue
except Exception as e:
    print(f"Error analyzing CSV: {str(e)}")
