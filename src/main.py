import argparse
import sys
from pathlib import Path

from src.common.symbol_table import SymbolTable
from src.lexer.lexer_framework import LexicalAnalyzerFramework
from src.parser.slr_framework import ParserGeneratorFramework


def run_lexer_only(er_file: Path, source_file: Path, out_tokens: Path, show_tables: bool) -> None:
    lex = LexicalAnalyzerFramework()
    lex.build_from_definitions_text(er_file.read_text(encoding="utf-8"))
    if show_tables:
        print(lex.visualize_automata())
        print()
        print(lex.visualize_lexical_table())
        print()

    tokens = lex.tokenize(source_file.read_text(encoding="utf-8"))
    lines = [t.to_lexer_str() for t in tokens]
    out_tokens.parent.mkdir(parents=True, exist_ok=True)
    out_tokens.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    for line in lines:
        print(line)


def run_integrated(
    er_file: Path,
    glc_file: Path,
    pr_file: Path,
    source_file: Path,
    out_tokens: Path,
    out_stack: Path,
    show_tables: bool,
) -> None:
    reserved = [
        line.strip()
        for line in pr_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    sym_table = SymbolTable(reserved_words=reserved)

    lex = LexicalAnalyzerFramework()
    lex.build_from_definitions_text(er_file.read_text(encoding="utf-8"), symbol_table=sym_table)
    if show_tables:
        print(lex.visualize_lexical_table())
        print()

    tokens = lex.tokenize(source_file.read_text(encoding="utf-8"))
    out_tokens.parent.mkdir(parents=True, exist_ok=True)
    out_tokens.write_text("\n".join(t.to_lexer_str() for t in tokens) + "\n", encoding="utf-8")

    parser_gen = ParserGeneratorFramework()
    slr_table = parser_gen.build_from_grammar(glc_file.read_text(encoding="utf-8"))
    if slr_table.conflicts:
        print("AVISO - Conflitos SLR detectados:")
        for c in slr_table.conflicts:
            print("  -", c)

    result = parser_gen.parse(tokens, symbol_table=sym_table)
    stack_lines = [
        f"Passo {st.step:>2} | Pilha: {st.stack_str} | Entrada: {st.input_str} | Ação: {st.action}"
        for st in result.steps
    ]
    stack_lines.append("")
    stack_lines.append(f"Resultado: {result.message}")
    stack_lines.append("")
    stack_lines.append(sym_table.format_table())

    out_stack.parent.mkdir(parents=True, exist_ok=True)
    out_stack.write_text("\n".join(stack_lines) + "\n", encoding="utf-8")

    print("\n".join(stack_lines))
    if not result.accepted:
        sys.exit(1)


def main() -> None:
    # Mantem a notacao ⟨lexema, token⟩ legivel no console do Windows.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="Arcabouco GALS - INE5421 (Lexico + Sintatico SLR)")
    sub = ap.add_subparsers(dest="command", required=True)

    p_lex = sub.add_parser("lex", help="Executa apenas o Gerador/Analisador Lexico (Trabalho 1)")
    p_lex.add_argument("--er", required=True, type=Path)
    p_lex.add_argument("--fonte", required=True, type=Path)
    p_lex.add_argument("--out", default=Path("out/tokens.txt"), type=Path)
    p_lex.add_argument("--tabelas", action="store_true")

    p_full = sub.add_parser("compilar", help="Executa Lexico + TS + Sintatico SLR integrado (Trabalho 1 + 2)")
    p_full.add_argument("--er", required=True, type=Path)
    p_full.add_argument("--glc", required=True, type=Path)
    p_full.add_argument("--pr", required=True, type=Path)
    p_full.add_argument("--fonte", required=True, type=Path)
    p_full.add_argument("--out-tokens", default=Path("out/tokens.txt"), type=Path)
    p_full.add_argument("--out-pilha", default=Path("out/pilha_execucao.txt"), type=Path)
    p_full.add_argument("--tabelas", action="store_true")

    args = ap.parse_args()
    if args.command == "lex":
        run_lexer_only(args.er, args.fonte, args.out, args.tabelas)
    elif args.command == "compilar":
        run_integrated(args.er, args.glc, args.pr, args.fonte, args.out_tokens, args.out_pilha, args.tabelas)


if __name__ == "__main__":
    main()
