import os

PROJECT_ROOT = r"C:\Users\10294484\Desktop\AI DEMO\ALARM MANAGER"
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "PROGETTO_COMPLETO_ALARM_MANAGER.txt")

INCLUDED_EXTENSIONS = ['.py', '.jsx', '.css', '.html', '.json', '.bat', 'Dockerfile', '.md']
EXCLUDED_DIRS = ['node_modules', 'dist', 'venv', 'backend/venv', '.git', '__pycache__', 'data', 'uploads']

def is_excluded(path):
    for d in EXCLUDED_DIRS:
        if d in path.replace('\\', '/'):
            return True
    return False

with open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
    outfile.write("="*80 + "\n")
    outfile.write(" MW ALARM MANAGER - CODICE COMPLETO PROGETTO\n")
    outfile.write("="*80 + "\n\n")
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if not is_excluded(os.path.join(root, d))]
        
        for file in files:
            ext = os.path.splitext(file)[1]
            if file == "PROGETTO_COMPLETO_ALARM_MANAGER.txt" or file.endswith('.xlsx') or file.endswith('.parquet'):
                continue
            if ext in INCLUDED_EXTENSIONS or file in INCLUDED_EXTENSIONS:
                filepath = os.path.join(root, file)
                if is_excluded(filepath):
                    continue
                
                rel_path = os.path.relpath(filepath, PROJECT_ROOT)
                outfile.write(f"\n\n{'='*80}\n")
                outfile.write(f" FILE: {rel_path}\n")
                outfile.write(f"{'='*80}\n\n")
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"[Errore lettura file: {e}]\n")

print(f"File di riepilogo generato in: {OUTPUT_FILE}")
