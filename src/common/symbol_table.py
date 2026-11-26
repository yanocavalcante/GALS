from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Token:
    lexeme: str
    pattern: str
    attr: Optional[object] = None

    def _display_pair(self) -> Tuple[str, str]:
        """Retorna uma representacao curta para arquivos e tracos de execucao."""
        if len(self.lexeme) == 1 and self.lexeme in "{}()=+;":
            return self.lexeme, self.lexeme
        if self.pattern == "PR":
            return self.lexeme, "PR"
        if self.attr is not None:
            return self.pattern, str(self.attr)
        return self.lexeme, self.pattern

    def to_lexer_str(self) -> str:
        lexeme, token = self._display_pair()
        return f"⟨{lexeme}, {token}⟩"

    def to_parser_str(self) -> str:
        if self.pattern == "id" and self.attr is not None:
            return f"⟨id, {self.attr}⟩"
        lexeme, token = self._display_pair()
        return f"⟨{lexeme}, {token}⟩"


@dataclass
class SymbolEntry:
    index: int
    lexeme: str
    category: str  # "PR" (Palavra-Reservada), "id", "const", etc.
    token_pattern: str


class SymbolTable:
    """Tabela de Simbolos (TS) com pre-carga de palavras reservadas."""

    def __init__(self, reserved_words: Optional[List[str]] = None) -> None:
        self.entries: List[SymbolEntry] = []
        self._index_by_lexeme: Dict[str, int] = {}
        if reserved_words:
            for word in reserved_words:
                self.add_reserved_word(word)

    def add_reserved_word(self, lexeme: str) -> SymbolEntry:
        if lexeme in self._index_by_lexeme:
            idx = self._index_by_lexeme[lexeme]
            return self.entries[idx]
        idx = len(self.entries)
        entry = SymbolEntry(
            index=idx,
            lexeme=lexeme,
            category="PR",
            token_pattern="PR",
        )
        self.entries.append(entry)
        self._index_by_lexeme[lexeme] = idx
        return entry

    def lookup(self, lexeme: str) -> Optional[SymbolEntry]:
        idx = self._index_by_lexeme.get(lexeme)
        return self.entries[idx] if idx is not None else None

    def insert_or_resolve(self, lexeme: str, default_pattern: str = "id") -> Tuple[SymbolEntry, Token]:
        """
        Regra da especificacao:
        - Se o lexema ja estiver na TS e for palavra reservada ('PR'), retorna (lexema, PR).
        - Se ja estiver na TS como identificador/variavel, retorna (id, linha_TS).
        - Caso contrario, insere na TS e retorna (id, linha_TS).
        """
        existing = self.lookup(lexeme)
        if existing is not None:
            if existing.category == "PR":
                return existing, Token(lexeme=existing.lexeme, pattern="PR", attr="PR")
            return existing, Token(lexeme=lexeme, pattern=default_pattern, attr=existing.index)

        idx = len(self.entries)
        entry = SymbolEntry(
            index=idx,
            lexeme=lexeme,
            category=default_pattern,
            token_pattern=default_pattern,
        )
        self.entries.append(entry)
        self._index_by_lexeme[lexeme] = idx
        return entry, Token(lexeme=lexeme, pattern=default_pattern, attr=idx)

    def format_table(self) -> str:
        lines = ["Linha | Lexema       | Categoria | Padrao"]
        lines.append("-" * 46)
        for e in self.entries:
            lines.append(f"{e.index:<5} | {e.lexeme:<12} | {e.category:<9} | {e.token_pattern}")
        return "\n".join(lines)
