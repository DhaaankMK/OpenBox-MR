"""Verificação estática simples: nomes não definidos e atributos self.x usados mas nunca atribuídos."""
import ast, builtins, os, sys

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "openbox")
BUILTINS = set(dir(builtins)) | {"__file__", "__name__"}


def names_bound(node):
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            out.update(n.names)
    return out


def check_file(path):
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    problems = []
    mod_names = names_bound(tree)
    # nomes não definidos (aproximado: tudo que é ligado no arquivo conta como definido)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            if n.id not in mod_names and n.id not in BUILTINS:
                problems.append(f"{path}:{n.lineno}: nome não definido '{n.id}'")
    # atributos self.x
    classes = {c.name: c for c in ast.walk(tree) if isinstance(c, ast.ClassDef)}
    for c in classes.values():
        assigned = {n.name for n in c.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        for n in c.body:
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    for nm in ast.walk(t):
                        if isinstance(nm, ast.Name):
                            assigned.add(nm.id)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                assigned.add(n.target.id)
        for n in ast.walk(c):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" and isinstance(n.ctx, ast.Store):
                assigned.add(n.attr)
        # herança dentro do arquivo
        for b in c.bases:
            if isinstance(b, ast.Name) and b.id in classes:
                bc = classes[b.id]
                for n in ast.walk(bc):
                    if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" and isinstance(n.ctx, ast.Store):
                        assigned.add(n.attr)
                    if isinstance(n, (ast.FunctionDef,)):
                        assigned.add(n.name)
                for n in bc.body:
                    if isinstance(n, ast.Assign):
                        for t in n.targets:
                            if isinstance(t, ast.Name):
                                assigned.add(t.id)
        has_ext_base = any(not (isinstance(b, ast.Name) and b.id in classes) for b in c.bases)
        for n in ast.walk(c):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self" and isinstance(n.ctx, ast.Load):
                if n.attr not in assigned and not has_ext_base and not n.attr.startswith("__"):
                    problems.append(f"{path}:{n.lineno}: {c.name}.{n.attr} lido mas nunca atribuído")
    return problems


def main():
    probs = []
    for base, _, files in os.walk(ROOT):
        for f in files:
            if f.endswith(".py"):
                probs += check_file(os.path.join(base, f))
    for p in probs:
        print(p)
    print(f"{len(probs)} possíveis problemas")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
