"""
Replace all em-dashes (U+2014) and en-dashes (U+2013) in project source files.
Em-dash  -> ' - '  (space-hyphen-space, readable replacement in prose)
En-dash  -> '-'    (simple hyphen)
Skips: venv/, .git/, __pycache__/, migrations/
"""
import os
import glob

EM = '\u2014'
EN = '\u2013'

SKIP_DIRS = {'venv', '.venv', '.git', '__pycache__', 'migrations', 'node_modules', 'staticfiles'}

EXTENSIONS = {'.py', '.html', '.txt', '.md', '.toml', '.sh', '.bat'}

changed = []
errors = []

for root, dirs, files in os.walk('.'):
    # Prune skipped directories in-place
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        if ext not in EXTENSIONS:
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, encoding='utf-8') as f:
                original = f.read()
        except Exception as e:
            errors.append(f'READ ERROR {fpath}: {e}')
            continue

        if EM not in original and EN not in original:
            continue

        # Replace: em-dash with ' - ', en-dash with '-'
        updated = original.replace(EM, ' - ').replace(EN, '-')

        # Count replacements
        em_count = original.count(EM)
        en_count = original.count(EN)

        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(updated)
            changed.append(f'{fpath}  (em:{em_count} en:{en_count})')
        except Exception as e:
            errors.append(f'WRITE ERROR {fpath}: {e}')

print(f'\n=== Em-dash/En-dash removal complete ===')
print(f'Files changed: {len(changed)}')
for c in changed:
    print(f'  {c}')
if errors:
    print(f'\nErrors ({len(errors)}):')
    for e in errors:
        print(f'  {e}')
