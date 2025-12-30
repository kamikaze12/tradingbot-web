# analyze_repos.py
#!/usr/bin/env python3
"""
Analyze struktur semua external repos
"""

import os
import re
from pathlib import Path

def analyze_repo(repo_path):
    """Analyze satu repo"""
    print(f"\n{'='*60}")
    print(f"📁 Analyzing: {repo_path.name}")
    print(f"{'='*60}")
    
    if not repo_path.exists():
        print("❌ Folder tidak ditemukan")
        return
    
    # Cek struktur
    print("📂 Structure:")
    for root, dirs, files in os.walk(repo_path):
        level = root.replace(str(repo_path), '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            if file.endswith('.py'):
                print(f"{subindent}📄 {file}")
    
    # Cari dan analisis file Python
    py_files = list(repo_path.rglob("*.py"))
    if not py_files:
        print("⚠️  Tidak ada file Python")
        return
    
    print(f"\n🔍 Found {len(py_files)} Python files:")
    
    for py_file in py_files[:5]:  # Analisis 5 file pertama
        print(f"\n  📄 {py_file.relative_to(repo_path)}:")
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Cari class definitions
            classes = re.findall(r'class\s+(\w+)', content)
            if classes:
                print(f"    🏷️  Classes: {', '.join(classes)}")
            
            # Cari import statements
            imports = re.findall(r'from\s+(\S+)\s+import|import\s+([\w\s,]+)', content)
            if imports:
                print(f"    📦 Imports: {imports[:3]}...")  # Show first 3
            
            # Cari function definitions
            functions = re.findall(r'def\s+(\w+)', content)
            if functions:
                print(f"    ⚙️  Functions: {', '.join(functions[:5])}...")
                
            # Cari main/entry point
            if 'if __name__' in content:
                print(f"    🚀 Has __main__ block")
                
        except Exception as e:
            print(f"    ❌ Error reading file: {e}")
    
    # Cari README atau dokumentasi
    readme_files = list(repo_path.glob("README*"))
    if readme_files:
        print(f"\n📖 Documentation:")
        for readme in readme_files[:2]:
            try:
                with open(readme, 'r', encoding='utf-8', errors='ignore') as f:
                    first_lines = [f.readline().strip() for _ in range(5)]
                print(f"  📄 {readme.name}:")
                for line in first_lines:
                    if line:
                        print(f"    {line}")
            except:
                pass

def main():
    base_path = Path("bot/external_repos")
    
    if not base_path.exists():
        print("❌ Folder bot/external_repos tidak ditemukan!")
        return
    
    print("🔍 ANALYZING EXTERNAL REPOSITORIES")
    print("="*60)
    
    # List semua repos
    repos = []
    for item in base_path.iterdir():
        if item.is_dir():
            repos.append(item)
    
    print(f"Found {len(repos)} repositories:")
    for i, repo in enumerate(repos, 1):
        print(f"{i:2}. {repo.name}")
    
    # Analisis repos penting
    important_repos = [
        "ForexScraper",
        "indonesia_stocks_scraper", 
        "Investing_com_Scraper",
        "Crypto_History_Scraper_BinanceApi",
        "ForexTrackerpro",
        "Forex_analyzer_X_scrapper"
    ]
    
    for repo_name in important_repos:
        repo_path = base_path / repo_name
        if repo_path.exists():
            analyze_repo(repo_path)
        else:
            print(f"\n⚠️  {repo_name} tidak ditemukan!")

if __name__ == "__main__":
    main()
