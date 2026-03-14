import importlib
import os
import sys

def test_imports():
    modules = [
        "config",
        "database",
        "models",
        "schemas",
        "auth",
        "dependencies",
        "sentiment",
        "llm_adapter",
        "llamacpp",
        "services",
        "oauth_routes",
        "routes.npc_routes",
        "routes.build_routes",
        "routes.player_routes",
        "routes.consent_routes",
        "main"
    ]
    
    print("🚀 Starting module import test...")
    failures = 0
    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
            print(f"✅ {mod_name}: OK")
        except Exception as e:
            print(f"❌ {mod_name}: FAILED - {e}")
            failures += 1
            
    if failures == 0:
        print("\n✨ All modules imported successfully!")
    else:
        print(f"\n⚠️ Import test failed with {failures} errors.")
        sys.exit(1)

if __name__ == "__main__":
    # Force test environment to use SQLite
    os.environ["ENVIRONMENT"] = "test"
    test_imports()
