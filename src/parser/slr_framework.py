from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from src.common.symbol_table import SymbolTable, Token

EPSILON = "&"
EOF_SYM = "$"


@dataclass(frozen=True)
class Production:
    index: int
    lhs: str  # Ex.: "⟨S⟩"
    rhs: Tuple[str, ...]  # Ex.: ("⟨A⟩", "id", ";") ou ("&",)

    def __str__(self) -> str:
        body = " ".join(self.rhs) if self.rhs else EPSILON
        return f"({self.index}) {self.lhs} ::= {body}"


@dataclass(frozen=True)
class LRItem:
    prod_index: int
    dot: int  # posicao do ponto: 0 .. len(rhs)

    def is_complete(self, productions: List[Production]) -> bool:
        prod = productions[self.prod_index]
        if prod.rhs == (EPSILON,):
            return True
        return self.dot >= len(prod.rhs)

    def next_symbol(self, productions: List[Production]) -> Optional[str]:
        prod = productions[self.prod_index]
        if prod.rhs == (EPSILON,) or self.dot >= len(prod.rhs):
            return None
        return prod.rhs[self.dot]

    def advance(self, productions: List[Production]) -> "LRItem":
        prod = productions[self.prod_index]
        if prod.rhs == (EPSILON,):
            return LRItem(self.prod_index, len(prod.rhs))
        return LRItem(self.prod_index, self.dot + 1)


def is_non_terminal(sym: str) -> bool:
    return sym.startswith("⟨") and sym.endswith("⟩") and len(sym) > 2


def parse_grammar_text(grammar_text: str) -> Tuple[List[Production], str, Set[str], Set[str]]:
    """
    Le uma GLC no formato:
      ⟨Nao terminal⟩ ::= ⟨Corpo da producao⟩
    Nao terminais aparecem entre ⟨ e ⟩.
    Caracteres especiais literais podem aparecer entre aspas "", ex.: "[" ou "]".
    Simbolo de escape / vazio: &.
    """
    productions: List[Production] = []
    non_terminals: Set[str] = set()
    terminals: Set[str] = set()
    start_nt: Optional[str] = None

    for raw_line in grammar_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "::=" not in line:
            raise ValueError(f"Producao invalida (esperado ::=): {line}")
        lhs_raw, rhs_raw = line.split("::=", 1)
        lhs = lhs_raw.strip()
        if not is_non_terminal(lhs):
            raise ValueError(f"Nao terminal invalido no lado esquerdo: {lhs}")
        if start_nt is None:
            start_nt = lhs
        non_terminals.add(lhs)

        # Tokeniza corpo da producao respeitando ⟨...⟩, "..." e escape &
        rhs_tokens: List[str] = []
        i = 0
        n = len(rhs_raw)
        while i < n:
            ch = rhs_raw[i]
            if ch.isspace():
                i += 1
                continue
            if ch == "&":
                if i + 1 < n and not rhs_raw[i + 1].isspace() and rhs_raw[i + 1] not in {"⟨", '"'}:
                    # Escape & seguido de caractere
                    rhs_tokens.append(rhs_raw[i + 1])
                    i += 2
                else:
                    rhs_tokens.append(EPSILON)
                    i += 1
            elif ch == "⟨":
                end_p = rhs_raw.find("⟩", i + 1)
                if end_p == -1:
                    raise ValueError(f"Nao terminal nao fechado em: {line}")
                nt = rhs_raw[i : end_p + 1].strip()
                rhs_tokens.append(nt)
                non_terminals.add(nt)
                i = end_p + 1
            elif ch == '"':
                end_q = rhs_raw.find('"', i + 1)
                if end_q == -1:
                    raise ValueError(f"Literal entre aspas nao fechado em: {line}")
                lit = rhs_raw[i + 1 : end_q]
                rhs_tokens.append(lit)
                terminals.add(lit)
                i = end_q + 1
            else:
                # Le simbolo/token ate espaco, ⟨ ou "
                start_s = i
                while i < n and not rhs_raw[i].isspace() and rhs_raw[i] not in {"⟨", '"'}:
                    if rhs_raw[i] == "&" and i + 1 < n:
                        i += 2
                    else:
                        i += 1
                sym = rhs_raw[start_s:i]
                if sym and sym != EPSILON:
                    rhs_tokens.append(sym)
                    terminals.add(sym)

        if not rhs_tokens:
            rhs_tokens = [EPSILON]

        productions.append(
            Production(index=len(productions), lhs=lhs, rhs=tuple(rhs_tokens))
        )

    if start_nt is None:
        raise ValueError("Gramatica vazia.")

    # Aumenta gramatica com ⟨S'⟩ ::= ⟨S⟩
    aug_lhs = f"{start_nt[:-1]}'⟩"
    while aug_lhs in non_terminals:
        aug_lhs = f"{aug_lhs[:-1]}'⟩"
    aug_prod = Production(index=0, lhs=aug_lhs, rhs=(start_nt,))
    shifted_prods = [aug_prod]
    for p in productions:
        shifted_prods.append(Production(index=len(shifted_prods), lhs=p.lhs, rhs=p.rhs))

    non_terminals.add(aug_lhs)
    return shifted_prods, aug_lhs, non_terminals, terminals


def compute_first_follow(
    productions: List[Production],
    start_nt: str,
    non_terminals: Set[str],
    terminals: Set[str],
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Algoritmos First e Follow (Aho, secao 4.4.2)."""
    first: Dict[str, Set[str]] = {nt: set() for nt in non_terminals}
    for t in terminals:
        first[t] = {t}
    first[EPSILON] = {EPSILON}
    first[EOF_SYM] = {EOF_SYM}

    changed = True
    while changed:
        changed = False
        for prod in productions:
            if prod.rhs == (EPSILON,):
                if EPSILON not in first[prod.lhs]:
                    first[prod.lhs].add(EPSILON)
                    changed = True
                continue

            all_nullable = True
            for sym in prod.rhs:
                sym_first = first.setdefault(sym, {sym})
                for f in sym_first:
                    if f != EPSILON and f not in first[prod.lhs]:
                        first[prod.lhs].add(f)
                        changed = True
                if EPSILON not in sym_first:
                    all_nullable = False
                    break
            if all_nullable and EPSILON not in first[prod.lhs]:
                first[prod.lhs].add(EPSILON)
                changed = True

    follow: Dict[str, Set[str]] = {nt: set() for nt in non_terminals}
    follow[start_nt].add(EOF_SYM)

    changed = True
    while changed:
        changed = False
        for prod in productions:
            rhs = prod.rhs
            if rhs == (EPSILON,):
                continue
            for i, sym in enumerate(rhs):
                if not is_non_terminal(sym):
                    continue
                beta = rhs[i + 1 :]
                if beta:
                    beta_first: Set[str] = set()
                    beta_nullable = True
                    for b in beta:
                        b_f = first.get(b, {b})
                        beta_first |= {x for x in b_f if x != EPSILON}
                        if EPSILON not in b_f:
                            beta_nullable = False
                            break
                    before = len(follow[sym])
                    follow[sym] |= beta_first
                    if beta_nullable:
                        follow[sym] |= follow[prod.lhs]
                    if len(follow[sym]) > before:
                        changed = True
                else:
                    before = len(follow[sym])
                    follow[sym] |= follow[prod.lhs]
                    if len(follow[sym]) > before:
                        changed = True

    return first, follow


def closure(items: Set[LRItem], productions: List[Production]) -> Set[LRItem]:
    """Algoritmo Closure (Aho, figura 4.32)."""
    result = set(items)
    added = True
    while added:
        added = False
        new_items: Set[LRItem] = set()
        for it in result:
            sym = it.next_symbol(productions)
            if sym and is_non_terminal(sym):
                for prod in productions:
                    if prod.lhs == sym:
                        cand = LRItem(prod_index=prod.index, dot=0)
                        if cand not in result:
                            new_items.add(cand)
        if new_items:
            result |= new_items
            added = True
    return result


def goto(items: Set[LRItem], symbol: str, productions: List[Production]) -> Set[LRItem]:
    moved: Set[LRItem] = set()
    for it in items:
        if it.next_symbol(productions) == symbol:
            moved.add(it.advance(productions))
    return closure(moved, productions) if moved else set()


def canonical_collection(
    productions: List[Production],
    aug_start_nt: str,
    non_terminals: Set[str],
    terminals: Set[str],
) -> Tuple[List[Set[LRItem]], Dict[Tuple[int, str], int]]:
    """Algoritmo de construcao da colecao canonica LR(0) (Aho, figura 4.33)."""
    start_prod = next(p for p in productions if p.lhs == aug_start_nt)
    c0 = closure({LRItem(prod_index=start_prod.index, dot=0)}, productions)
    states: List[Set[LRItem]] = [c0]
    transitions: Dict[Tuple[int, str], int] = {}
    all_symbols = sorted(terminals | non_terminals)

    idx = 0
    while idx < len(states):
        cur_set = states[idx]
        for sym in all_symbols:
            g = goto(cur_set, sym, productions)
            if not g:
                continue
            if g not in states:
                target_idx = len(states)
                states.append(g)
            else:
                target_idx = states.index(g)
            transitions[(idx, sym)] = target_idx
        idx += 1

    return states, transitions


@dataclass
class SLRTable:
    action: Dict[Tuple[int, str], str] = field(default_factory=dict)  # "sN", "rK", "acc"
    goto_table: Dict[Tuple[int, str], int] = field(default_factory=dict)
    conflicts: List[str] = field(default_factory=list)


def build_slr_table(
    productions: List[Production],
    aug_start_nt: str,
    states: List[Set[LRItem]],
    transitions: Dict[Tuple[int, str], int],
    follow: Dict[str, Set[str]],
    terminals: Set[str],
    non_terminals: Set[str],
) -> SLRTable:
    """Algoritmo 4.38 - Construcao da tabela do analisador SLR."""
    table = SLRTable()
    start_prod = next(p for p in productions if p.lhs == aug_start_nt)

    for s_idx, item_set in enumerate(states):
        for it in item_set:
            nxt = it.next_symbol(productions)
            if nxt is not None and nxt in terminals:
                target = transitions.get((s_idx, nxt))
                if target is not None:
                    act = f"s{target}"
                    prev = table.action.get((s_idx, nxt))
                    if prev and prev != act:
                        table.conflicts.append(f"Conflito em Estado {s_idx}, sim '{nxt}': {prev} vs {act}")
                    table.action[(s_idx, nxt)] = act

            if it.is_complete(productions):
                if it.prod_index == start_prod.index:
                    table.action[(s_idx, EOF_SYM)] = "acc"
                else:
                    prod = productions[it.prod_index]
                    act = f"r{prod.index}"
                    for a in follow.get(prod.lhs, set()):
                        prev = table.action.get((s_idx, a))
                        if prev and prev != act:
                            table.conflicts.append(f"Conflito em Estado {s_idx}, sim '{a}': {prev} vs {act}")
                        table.action[(s_idx, a)] = act

        for nt in non_terminals:
            if nt == aug_start_nt:
                continue
            target = transitions.get((s_idx, nt))
            if target is not None:
                table.goto_table[(s_idx, nt)] = target

    return table


@dataclass
class ParseStep:
    step: int
    stack_str: str
    input_str: str
    action: str


@dataclass
class ParseResult:
    accepted: bool
    steps: List[ParseStep]
    message: str


def map_token_to_grammar_symbol(tok: Token, symbol_table: Optional[SymbolTable], terminals: Set[str]) -> str:
    """Mapeia o token do lexico para o simbolo terminal esperado na GLC."""
    if tok.pattern == "PR":
        if tok.lexeme in terminals:
            return tok.lexeme
        return "PR"
    if tok.lexeme in terminals:
        return tok.lexeme
    if tok.pattern in terminals:
        return tok.pattern
    if tok.pattern == "id" and "id" in terminals:
        return "id"
    return tok.pattern


def parse_tokens_lr(
    tokens: List[Token],
    productions: List[Production],
    aug_start_nt: str,
    slr_table: SLRTable,
    terminals: Set[str],
    symbol_table: Optional[SymbolTable] = None,
) -> ParseResult:
    """Algoritmo 4.44 (figura 4.36) - LR Parsing."""
    # Filtra tokens de erro lexico se houver
    lex_errors = [t for t in tokens if t.pattern == "erro!"]
    if lex_errors:
        bad = ", ".join(t.lexeme for t in lex_errors)
        return ParseResult(
            accepted=False,
            steps=[],
            message=f"Erro lexico encontrado antes da analise sintatica: {bad}",
        )

    mapped_stream: List[Tuple[str, str]] = []
    for t in tokens:
        sym = map_token_to_grammar_symbol(t, symbol_table, terminals)
        mapped_stream.append((sym, t.to_parser_str()))
    mapped_stream.append((EOF_SYM, "$"))

    stack: List[object] = [0]
    cursor = 0
    steps: List[ParseStep] = []
    step_num = 1

    while True:
        state = stack[-1]
        assert isinstance(state, int)
        cur_sym, _ = mapped_stream[cursor]
        act = slr_table.action.get((state, cur_sym))

        stack_repr = " ".join(str(x) for x in stack)
        rem_repr = " ".join(disp for _, disp in mapped_stream[cursor:])

        if act is None:
            steps.append(
                ParseStep(
                    step=step_num,
                    stack_str=stack_repr,
                    input_str=rem_repr,
                    action=f"ERRO SINTATICO (esperado em estado {state} para '{cur_sym}')",
                )
            )
            return ParseResult(
                accepted=False,
                steps=steps,
                message=f"Codigo sintaticamente INCORRETO no passo {step_num} com simbolo '{cur_sym}' (estado {state}).",
            )

        if act.startswith("s"):
            next_state = int(act[1:])
            steps.append(
                ParseStep(
                    step=step_num,
                    stack_str=stack_repr,
                    input_str=rem_repr,
                    action=f"Shift -> {next_state}",
                )
            )
            stack.append(cur_sym)
            stack.append(next_state)
            cursor += 1
            step_num += 1

        elif act.startswith("r"):
            prod_idx = int(act[1:])
            prod = productions[prod_idx]
            pop_len = 0 if prod.rhs == (EPSILON,) else len(prod.rhs) * 2
            steps.append(
                ParseStep(
                    step=step_num,
                    stack_str=stack_repr,
                    input_str=rem_repr,
                    action=f"Reduce by {prod.lhs} ::= {' '.join(prod.rhs)}",
                )
            )
            for _ in range(pop_len):
                stack.pop()
            top_state = stack[-1]
            assert isinstance(top_state, int)
            goto_state = slr_table.goto_table.get((top_state, prod.lhs))
            if goto_state is None:
                return ParseResult(
                    accepted=False,
                    steps=steps,
                    message=f"Erro de GOTO apos reducao de {prod.lhs} no estado {top_state}.",
                )
            stack.append(prod.lhs)
            stack.append(goto_state)
            step_num += 1

        elif act == "acc":
            steps.append(
                ParseStep(
                    step=step_num,
                    stack_str=stack_repr,
                    input_str=rem_repr,
                    action="ACCEPT",
                )
            )
            return ParseResult(
                accepted=True,
                steps=steps,
                message="Codigo sintaticamente CORRETO (ACEITO).",
            )


@dataclass
class ParserGeneratorFramework:
    productions: List[Production] = field(default_factory=list)
    aug_start_nt: str = ""
    non_terminals: Set[str] = field(default_factory=set)
    terminals: Set[str] = field(default_factory=set)
    first: Dict[str, Set[str]] = field(default_factory=dict)
    follow: Dict[str, Set[str]] = field(default_factory=dict)
    states: List[Set[LRItem]] = field(default_factory=list)
    transitions: Dict[Tuple[int, str], int] = field(default_factory=dict)
    slr_table: SLRTable = field(default_factory=SLRTable)

    def build_from_grammar(self, grammar_text: str) -> SLRTable:
        self.productions, self.aug_start_nt, self.non_terminals, self.terminals = parse_grammar_text(grammar_text)
        self.first, self.follow = compute_first_follow(
            self.productions, self.aug_start_nt, self.non_terminals, self.terminals
        )
        self.states, self.transitions = canonical_collection(
            self.productions, self.aug_start_nt, self.non_terminals, self.terminals
        )
        self.slr_table = build_slr_table(
            self.productions,
            self.aug_start_nt,
            self.states,
            self.transitions,
            self.follow,
            self.terminals,
            self.non_terminals,
        )
        return self.slr_table

    def parse(self, tokens: List[Token], symbol_table: Optional[SymbolTable] = None) -> ParseResult:
        return parse_tokens_lr(
            tokens=tokens,
            productions=self.productions,
            aug_start_nt=self.aug_start_nt,
            slr_table=self.slr_table,
            terminals=self.terminals,
            symbol_table=symbol_table,
        )
