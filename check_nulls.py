import os

def check_null_bytes():
    exclude = {'.venv', '.git', '__pycache__', '.pytest_cache'}
    py_files = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))
                
    print(f"🕵️ Checking {len(py_files)} source files for null bytes...")
    found = False
    for path in py_files:
        try:
            with open(path, 'rb') as f:
                content = f.read()
                count = content.count(b'\x00')
                if count > 0:
                    print(f"⚠️ {path}: {count} null bytes found")
                    found = True
        except Exception as e:
            print(f"❌ Error checking {path}: {e}")
            
    if not found:
        print("✨ No null bytes found in source Python files.")

if __name__ == "__main__":
    check_null_bytes()
