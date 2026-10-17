import os
p = 'scripts/run_p1_experiment_v2.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()
# The corrupted line has os.environ.get" (missing paren) - fix it
old = 'os.environ.get"'
new = 'os.environ.get("'
content = content.replace(old, new)
with open(p, 'w', encoding='utf-8') as f:
    f.write(content)
print('done')
