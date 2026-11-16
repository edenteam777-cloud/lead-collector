from pathlib import Path
p = Path(r"D:/Projetos/lead/_gerar_abordagens_sp_20261014.py")
s = p.read_text(encoding="utf-8")
new = Path(r"D:/Projetos/lead/_main_pagina_sp.txt").read_text(encoding="utf-8")
i, j = s.index("def main():"), s.index('if __name__ == "__main__":')
p.write_text(s[:i] + new + s[j:], encoding="utf-8")
print("patched")
