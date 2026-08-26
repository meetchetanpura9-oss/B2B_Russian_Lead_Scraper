import os

def format_env_to_toml():
    env_path = ".env"
    toml_path = "secrets_toml.txt"
    
    if not os.path.exists(env_path):
        print(f"Error: .env file not found at {env_path}")
        return
        
    lines = []
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # TOML requires strings to be enclosed in quotes
                lines.append(f'{key} = "{val}"')
                
    with open(toml_path, "w", encoding="utf-8") as f:
        f.write("# Copy and paste everything below into the Streamlit Secrets box:\n\n")
        f.write("\n".join(lines))
        f.write("\n")
        
    print(f"Success! Formatted secrets written to local file: {os.path.abspath(toml_path)}")

if __name__ == "__main__":
    format_env_to_toml()
