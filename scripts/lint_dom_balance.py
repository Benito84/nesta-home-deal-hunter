"""
Linter Balansu DOM dla Szablonów Jinja2 (Sekcja 4.6 Standardu Nesta Home).
Weryfikuje czy wszystkie tagi HTML (div, span, p, form, table, etc.) są poprawnie otwarte i domknięte.
"""

import sys
import re
from pathlib import Path
from html.parser import HTMLParser

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

SELF_CLOSING_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}

TAGS_TO_CHECK = {"div", "span", "p", "form", "table", "tbody", "thead", "tr", "td", "th", "ul", "ol", "li", "section", "article", "header", "footer", "nav", "main"}

class DOMBalanceChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower in TAGS_TO_CHECK and tag_lower not in SELF_CLOSING_TAGS:
            self.stack.append((tag_lower, self.getpos()))

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower in TAGS_TO_CHECK and tag_lower not in SELF_CLOSING_TAGS:
            if not self.stack:
                self.errors.append(f"Nieoczekiwany tag zamykający </{tag_lower}> na linii {self.getpos()[0]}")
                return
            last_tag, pos = self.stack.pop()
            if last_tag != tag_lower:
                self.errors.append(
                    f"Niezgodność tagu: oczekiwano </{last_tag}> (otwartego na linii {pos[0]}), a napotkano </{tag_lower}> na linii {self.getpos()[0]}"
                )

def strip_jinja_syntax(content: str) -> str:
    # Usuwamy komentarze Jinja {# ... #}
    content = re.sub(r'\{#.*?#\}', '', content, flags=re.DOTALL)
    # Usuwamy bloki Jinja {% ... %}
    content = re.sub(r'\{%.*?%\}', '', content, flags=re.DOTALL)
    # Usuwamy wyrażenia Jinja {{ ... }}
    content = re.sub(r'\{\{.*?\}\}', 'EXPR', content, flags=re.DOTALL)
    return content

def lint_templates(templates_dir: Path) -> bool:
    print(f"--- [DOM Balance Linter] Skanowanie szablonów w: {templates_dir} ---")
    all_passed = True
    html_files = list(templates_dir.glob("**/*.html"))

    if not html_files:
        print("Nie znaleziono plików HTML do weryfikacji.")
        return True

    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        clean_html = strip_jinja_syntax(content)
        
        checker = DOMBalanceChecker()
        try:
            checker.feed(clean_html)
            checker.close()
        except Exception as e:
            print(f"[BŁĄD PARSOWANIA] {html_file.name}: {e}")
            all_passed = False
            continue

        errors = checker.errors
        for unclosed, pos in checker.stack:
            errors.append(f"Niedomknięty tag <{unclosed}> otwarty na linii {pos[0]}")

        if errors:
            all_passed = False
            print(f"❌ [BŁĄD] {html_file.name}:")
            for err in errors[:5]:
                print(f"   - {err}")
        else:
            print(f"✅ [OK] {html_file.name}")

    if all_passed:
        print("--- Wszystkie szablony mają poprawny i zbalansowany DOM! ---")
    return all_passed

if __name__ == "__main__":
    templates_path = Path(__file__).resolve().parent.parent / "app" / "web" / "templates"
    success = lint_templates(templates_path)
    sys.exit(0 if success else 1)
