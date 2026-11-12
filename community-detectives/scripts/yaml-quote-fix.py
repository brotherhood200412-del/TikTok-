"""Hilfswerkzeug für Autorinnen und Autoren: setzt Plain-Scalar-Werte mit ': ' oder ' #' in Anführungszeichen."""
import re, sys
pat = re.compile(r'^(\s*(?:- )?)([A-Za-z_][\w]*): (.+)$')
for path in sys.argv[1:]:
    out = []
    changed = 0
    for line in open(path, encoding='utf8').read().split('\n'):
        m = pat.match(line)
        if m:
            pre, key, val = m.groups()
            v = val.strip()
            if v and v[0] not in '"\'{[|>&*!' and (': ' in v or ' #' in v or v.endswith(':')):
                v2 = '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
                line = f'{pre}{key}: {v2}'
                changed += 1
        out.append(line)
    open(path, 'w', encoding='utf8').write('\n'.join(out))
    print(path, changed, 'Zeilen angepasst')
