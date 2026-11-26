from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from src.common.symbol_table import SymbolTable, Token

EPSILON = "&"
SYMBOL_TABLE_PATTERNS = {"id", "ID", "ident", "num", "NUM", "const", "CONST"}


@dataclass
class NFA:
    states: Set[int]
    alphabet: Set[str]
    transitions: Dict[Tuple[int, str], Set[int]]
    start_state: int
    accept_states: Dict[int, str]  # state -> token_pattern


@dataclass
class DFA:
    states: Set[int]
    alphabet: Set[str]
    transitions: Dict[Tuple[int, str], int]
    start_state: int
    accept_states: Dict[int, str]  # state -> token_pattern
    name: str = "AFD"

    def to_table_str(self) -> str:
        syms = sorted(self.alphabet)
        header = ["Estado", "Papel", *syms]
        rows = []
        for s in sorted(self.states):
            roles = []
            if s == self.start_state:
                roles.append("Inicial")
            if s in self.accept_states:
                roles.append(f"Final({self.accept_states[s]})")
            role_str = ",".join(roles) if roles else "-"
            row = [str(s), role_str]
            for c in syms:
                t = self.transitions.get((s, c))
                row.append(str(t) if t is not None else "-")
            rows.append(row)
        widths = [max(len(r[i]) for r in ([header] + rows)) for i in range(len(header))]
        fmt = lambda r: " | ".join(r[i].ljust(widths[i]) for i in range(len(header)))
        sep = "-+-".join("-" * w for w in widths)
        return "\n".join([f"=== {self.name} ===", fmt(header), sep, *(fmt(r) for r in rows)])


def expand_char_class(expr: str) -> List[str]:
    """Expande classes como [a-zA-Z] ou [0-9] em lista de caracteres."""
    inner = expr[1:-1]
    chars: List[str] = []
    i = 0
    while i < len(inner):
        if inner[i] == "\\" and i + 1 < len(inner):
            chars.append(inner[i + 1])
            i += 2
        elif i + 2 < len(inner) and inner[i + 1] == "-":
            start_c, end_c = inner[i], inner[i + 2]
            for code in range(ord(start_c), ord(end_c) + 1):
                c = chr(code)
                if c not in chars:
                    chars.append(c)
            i += 3
        else:
            if inner[i] not in chars:
                chars.append(inner[i])
            i += 1
    return chars


def tokenize_regex(regex: str) -> List[Tuple[str, str]]:
    """
    Tokeniza uma ER em itens (KIND, VALUE):
    - CHAR: literal simples ou expandido de classe [a-z]
    - OR: |
    - STAR: *
    - PLUS: +
    - QMARK: ?
    - LPAREN: (
    - RPAREN: )
    - CONCAT: inserido explicitamente
    """
    raw: List[Tuple[str, str]] = []
    i = 0
    while i < len(regex):
        ch = regex[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "\\" and i + 1 < len(regex):
            raw.append(("CHAR", regex[i + 1]))
            i += 2
        elif ch == "[":
            end = regex.find("]", i + 1)
            if end == -1:
                raise ValueError(f"Classe de caracteres nao fechada em: {regex}")
            chars = expand_char_class(regex[i : end + 1])
            if not chars:
                raise ValueError(f"Classe de caracteres vazia em: {regex}")
            if len(chars) == 1:
                raw.append(("CHAR", chars[0]))
            else:
                raw.append(("LPAREN", "("))
                for idx, c in enumerate(chars):
                    if idx > 0:
                        raw.append(("OR", "|"))
                    raw.append(("CHAR", c))
                raw.append(("RPAREN", ")"))
            i = end + 1
        elif ch == "|":
            raw.append(("OR", "|"))
            i += 1
        elif ch == "*":
            raw.append(("STAR", "*"))
            i += 1
        elif ch == "+":
            raw.append(("PLUS", "+"))
            i += 1
        elif ch == "?":
            raw.append(("QMARK", "?"))
            i += 1
        elif ch == "(":
            raw.append(("LPAREN", "("))
            i += 1
        elif ch == ")":
            raw.append(("RPAREN", ")"))
            i += 1
        else:
            raw.append(("CHAR", ch))
            i += 1

    # Insere CONCAT implicita
    def can_end(kind: str) -> bool:
        return kind in {"CHAR", "RPAREN", "STAR", "PLUS", "QMARK"}

    def can_start(kind: str) -> bool:
        return kind in {"CHAR", "LPAREN"}

    with_concat: List[Tuple[str, str]] = []
    for idx, item in enumerate(raw):
        if idx > 0 and can_end(raw[idx - 1][0]) and can_start(item[0]):
            with_concat.append(("CONCAT", "."))
        with_concat.append(item)
    return with_concat


def regex_to_postfix(regex: str) -> List[Tuple[str, str]]:
    precedence = {"OR": 1, "CONCAT": 2, "STAR": 3, "PLUS": 3, "QMARK": 3}
    postfix: List[Tuple[str, str]] = []
    stack: List[Tuple[str, str]] = []
    for kind, val in tokenize_regex(regex):
        if kind == "CHAR":
            postfix.append((kind, val))
        elif kind == "LPAREN":
            stack.append((kind, val))
        elif kind == "RPAREN":
            while stack and stack[-1][0] != "LPAREN":
                postfix.append(stack.pop())
            if not stack:
                raise ValueError(f"Parenteses desbalanceados em: {regex}")
            stack.pop()
        elif kind in precedence:
            while stack and stack[-1][0] != "LPAREN":
                top_kind = stack[-1][0]
                if precedence.get(top_kind, 0) >= precedence[kind]:
                    postfix.append(stack.pop())
                else:
                    break
            stack.append((kind, val))
    while stack:
        top = stack.pop()
        if top[0] == "LPAREN":
            raise ValueError(f"Parenteses desbalanceados em: {regex}")
        postfix.append(top)
    return postfix


def regex_to_afd_aho(regex: str, pattern_name: str) -> DFA:
    """
    Conversao direta de Expressao Regular para AFD segundo o algoritmo de Aho
    (arvore sintatica, nullable, firstpos, lastpos, followpos e construcao de Dstates).
    """
    postfix = regex_to_postfix(regex)

    @dataclass
    class Node:
        kind: str  # LEAF, OR, CONCAT, STAR, PLUS, QMARK
        char: Optional[str] = None
        pos: Optional[int] = None
        left: Optional["Node"] = None
        right: Optional["Node"] = None

    pos_to_char: Dict[int, str] = {}
    alphabet: Set[str] = set()
    next_pos = 1
    stack: List[Node] = []

    for kind, val in postfix:
        if kind == "CHAR":
            if val == EPSILON:
                stack.append(Node(kind="LEAF", char=EPSILON, pos=None))
            else:
                p = next_pos
                next_pos += 1
                pos_to_char[p] = val
                alphabet.add(val)
                stack.append(Node(kind="LEAF", char=val, pos=p))
        elif kind in {"STAR", "PLUS", "QMARK"}:
            child = stack.pop()
            stack.append(Node(kind=kind, left=child))
        elif kind in {"OR", "CONCAT"}:
            right = stack.pop()
            left = stack.pop()
            stack.append(Node(kind=kind, left=left, right=right))

    if len(stack) != 1:
        raise ValueError(f"Expressao regular invalida: {regex}")

    # Aumenta ER com marcador final '#' na posicao next_pos
    end_pos = next_pos
    pos_to_char[end_pos] = "#"
    root = Node(kind="CONCAT", left=stack[0], right=Node(kind="LEAF", char="#", pos=end_pos))

    followpos: Dict[int, Set[int]] = {p: set() for p in pos_to_char}

    def eval_node(node: Node) -> Tuple[bool, Set[int], Set[int]]:
        if node.kind == "LEAF":
            if node.char == EPSILON or node.pos is None:
                return True, set(), set()
            return False, {node.pos}, {node.pos}

        if node.kind == "OR":
            assert node.left and node.right
            n1, f1, l1 = eval_node(node.left)
            n2, f2, l2 = eval_node(node.right)
            return n1 or n2, f1 | f2, l1 | l2

        if node.kind == "CONCAT":
            assert node.left and node.right
            n1, f1, l1 = eval_node(node.left)
            n2, f2, l2 = eval_node(node.right)
            for i in l1:
                followpos[i].update(f2)
            nullable = n1 and n2
            first = (f1 | f2) if n1 else f1
            last = (l1 | l2) if n2 else l2
            return nullable, first, last

        if node.kind == "STAR":
            assert node.left
            _, f1, l1 = eval_node(node.left)
            for i in l1:
                followpos[i].update(f1)
            return True, f1, l1

        if node.kind == "PLUS":
            assert node.left
            n1, f1, l1 = eval_node(node.left)
            for i in l1:
                followpos[i].update(f1)
            return n1, f1, l1

        if node.kind == "QMARK":
            assert node.left
            _, f1, l1 = eval_node(node.left)
            return True, f1, l1

        raise ValueError(f"No desconhecido: {node.kind}")

    _, root_firstpos, _ = eval_node(root)

    dstates_sets: List[frozenset] = [frozenset(root_firstpos)]
    unmarked: List[int] = [0]
    dfa_trans: Dict[Tuple[int, str], int] = {}
    accept_states: Dict[int, str] = {}

    if end_pos in dstates_sets[0]:
        accept_states[0] = pattern_name

    while unmarked:
        s_idx = unmarked.pop(0)
        cur_set = dstates_sets[s_idx]
        for sym in sorted(alphabet):
            u_set: Set[int] = set()
            for p in cur_set:
                if pos_to_char.get(p) == sym:
                    u_set.update(followpos[p])
            if not u_set:
                continue
            u_frozen = frozenset(u_set)
            if u_frozen not in dstates_sets:
                t_idx = len(dstates_sets)
                dstates_sets.append(u_frozen)
                unmarked.append(t_idx)
                if end_pos in u_frozen:
                    accept_states[t_idx] = pattern_name
            else:
                t_idx = dstates_sets.index(u_frozen)
            dfa_trans[(s_idx, sym)] = t_idx

    return DFA(
        states=set(range(len(dstates_sets))),
        alphabet=alphabet,
        transitions=dfa_trans,
        start_state=0,
        accept_states=accept_states,
        name=f"AFD_{pattern_name}",
    )


def minimize_dfa(dfa: DFA) -> DFA:
    """Minimiza um AFD via refinamento de particoes (Hopcroft/Moore)."""
    reachable: Set[int] = set()
    queue = [dfa.start_state]
    while queue:
        cur = queue.pop(0)
        if cur in reachable:
            continue
        reachable.add(cur)
        for c in dfa.alphabet:
            nxt = dfa.transitions.get((cur, c))
            if nxt is not None and nxt not in reachable:
                queue.append(nxt)

    # Particao inicial por tipo de aceitacao
    groups_map: Dict[Optional[str], Set[int]] = {}
    for s in sorted(reachable):
        tag = dfa.accept_states.get(s)
        groups_map.setdefault(tag, set()).add(s)

    partitions: List[Set[int]] = [g for g in groups_map.values() if g]

    changed = True
    while changed:
        changed = False
        new_partitions: List[Set[int]] = []
        state_to_part: Dict[int, int] = {}
        for idx, part in enumerate(partitions):
            for st in part:
                state_to_part[st] = idx

        for part in partitions:
            if len(part) <= 1:
                new_partitions.append(part)
                continue
            buckets: Dict[Tuple[Optional[int], ...], Set[int]] = {}
            for st in sorted(part):
                sig = tuple(
                    state_to_part[dfa.transitions[(st, c)]] if (st, c) in dfa.transitions else None
                    for c in sorted(dfa.alphabet)
                )
                buckets.setdefault(sig, set()).add(st)
            if len(buckets) > 1:
                changed = True
            new_partitions.extend(buckets.values())
        partitions = new_partitions

    # Garante que o grupo contendo start_state vire estado 0
    start_part_idx = next(i for i, p in enumerate(partitions) if dfa.start_state in p)
    if start_part_idx != 0:
        partitions[0], partitions[start_part_idx] = partitions[start_part_idx], partitions[0]

    state_to_new: Dict[int, int] = {}
    for new_id, part in enumerate(partitions):
        for st in part:
            state_to_new[st] = new_id

    min_trans: Dict[Tuple[int, str], int] = {}
    min_accept: Dict[int, str] = {}
    for new_id, part in enumerate(partitions):
        rep = next(iter(part))
        if rep in dfa.accept_states:
            min_accept[new_id] = dfa.accept_states[rep]
        for c in dfa.alphabet:
            target = dfa.transitions.get((rep, c))
            if target is not None and target in state_to_new:
                min_trans[(new_id, c)] = state_to_new[target]

    return DFA(
        states=set(range(len(partitions))),
        alphabet=set(dfa.alphabet),
        transitions=min_trans,
        start_state=0,
        accept_states=min_accept,
        name=f"{dfa.name}_Min",
    )


def union_dfas_with_epsilon(dfas: List[DFA]) -> NFA:
    """Une multiplos AFDs a partir de um novo estado inicial com transicoes '&'."""
    next_state = 1
    start_state = 0
    states: Set[int] = {start_state}
    alphabet: Set[str] = set()
    transitions: Dict[Tuple[int, str], Set[int]] = {}
    accept_states: Dict[int, str] = {}

    for dfa in dfas:
        mapping: Dict[int, int] = {}
        for s in sorted(dfa.states):
            mapping[s] = next_state
            states.add(next_state)
            next_state += 1

        alphabet.update(dfa.alphabet)
        transitions.setdefault((start_state, EPSILON), set()).add(mapping[dfa.start_state])

        for (src, sym), dst in dfa.transitions.items():
            transitions.setdefault((mapping[src], sym), set()).add(mapping[dst])

        for acc_s, pat in dfa.accept_states.items():
            accept_states[mapping[acc_s]] = pat

    return NFA(
        states=states,
        alphabet=alphabet,
        transitions=transitions,
        start_state=start_state,
        accept_states=accept_states,
    )


def determinize_nfa(nfa: NFA, priority_order: Optional[List[str]] = None, name: str = "AFD_Unificado") -> DFA:
    """Determiniza o AFND unificado por & (epsilon-closure e move)."""
    prio = {pat: idx for idx, pat in enumerate(priority_order or [])}

    def eps_closure(seed: Set[int]) -> Set[int]:
        closure = set(seed)
        stack = list(seed)
        while stack:
            cur = stack.pop()
            for nxt in nfa.transitions.get((cur, EPSILON), set()):
                if nxt not in closure:
                    closure.add(nxt)
                    stack.append(nxt)
        return closure

    def resolve_accept(state_set: Set[int]) -> Optional[str]:
        candidates = [nfa.accept_states[s] for s in state_set if s in nfa.accept_states]
        if not candidates:
            return None
        candidates.sort(key=lambda p: prio.get(p, len(prio)))
        return candidates[0]

    init_set = frozenset(eps_closure({nfa.start_state}))
    dstates: List[frozenset] = [init_set]
    unmarked: List[int] = [0]
    trans: Dict[Tuple[int, str], int] = {}
    accept: Dict[int, str] = {}

    init_pat = resolve_accept(set(init_set))
    if init_pat:
        accept[0] = init_pat

    while unmarked:
        idx = unmarked.pop(0)
        cur_set = dstates[idx]
        for sym in sorted(nfa.alphabet):
            moved: Set[int] = set()
            for st in cur_set:
                moved.update(nfa.transitions.get((st, sym), set()))
            if not moved:
                continue
            target_set = frozenset(eps_closure(moved))
            if target_set not in dstates:
                t_idx = len(dstates)
                dstates.append(target_set)
                unmarked.append(t_idx)
                pat = resolve_accept(set(target_set))
                if pat:
                    accept[t_idx] = pat
            else:
                t_idx = dstates.index(target_set)
            trans[(idx, sym)] = t_idx

    return DFA(
        states=set(range(len(dstates))),
        alphabet=set(nfa.alphabet),
        transitions=trans,
        start_state=0,
        accept_states=accept,
        name=name,
    )


@dataclass
class LexicalAnalyzerFramework:
    definitions: List[Tuple[str, str]] = field(default_factory=list)
    individual_dfas: List[DFA] = field(default_factory=list)
    minimized_dfas: List[DFA] = field(default_factory=list)
    unified_dfa: Optional[DFA] = None
    symbol_table: Optional[SymbolTable] = None
    ignored_chars: Set[str] = field(default_factory=lambda: {" ", "\t", "\r", "\n"})

    def build_from_definitions_text(self, text: str, symbol_table: Optional[SymbolTable] = None) -> DFA:
        self.symbol_table = symbol_table
        self.definitions = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(f"Definicao regular invalida (esperado def-reg: ER): {line}")
            name, expr = line.split(":", 1)
            self.definitions.append((name.strip(), expr.strip()))

        self.individual_dfas = []
        self.minimized_dfas = []
        for pat_name, expr in self.definitions:
            afd = regex_to_afd_aho(expr, pat_name)
            afd_min = minimize_dfa(afd)
            self.individual_dfas.append(afd)
            self.minimized_dfas.append(afd_min)

        nfa_union = union_dfas_with_epsilon(self.minimized_dfas)
        order = [name for name, _ in self.definitions]
        self.unified_dfa = determinize_nfa(nfa_union, priority_order=order, name="Tabela_Analise_Lexica")
        return self.unified_dfa

    def visualize_automata(self) -> str:
        parts = []
        for dfa in self.individual_dfas:
            parts.append(dfa.to_table_str())
        for m_dfa in self.minimized_dfas:
            parts.append(m_dfa.to_table_str())
        return "\n\n".join(parts)

    def visualize_lexical_table(self) -> str:
        if not self.unified_dfa:
            raise RuntimeError("Tabela lexica ainda nao gerada.")
        return self.unified_dfa.to_table_str()

    def tokenize(self, source_code: str) -> List[Token]:
        if not self.unified_dfa:
            raise RuntimeError("Analisador lexico nao foi gerado.")
        dfa = self.unified_dfa
        tokens: List[Token] = []
        i = 0
        n = len(source_code)

        while i < n:
            if source_code[i] in self.ignored_chars:
                i += 1
                continue

            # Maximal munch (maior casamento possivel)
            state = dfa.start_state
            last_accept_idx: Optional[int] = None
            last_accept_pat: Optional[str] = None
            cur = i

            while cur < n:
                ch = source_code[cur]
                nxt = dfa.transitions.get((state, ch))
                if nxt is None:
                    break
                state = nxt
                cur += 1
                if state in dfa.accept_states:
                    last_accept_idx = cur
                    last_accept_pat = dfa.accept_states[state]

            if last_accept_idx is not None and last_accept_pat is not None:
                lexeme = source_code[i:last_accept_idx]
                if self.symbol_table is not None and last_accept_pat in SYMBOL_TABLE_PATTERNS:
                    normalized_pattern = "id" if last_accept_pat in {"id", "ID", "ident"} else last_accept_pat
                    _, tok = self.symbol_table.insert_or_resolve(lexeme, default_pattern=normalized_pattern)
                    tokens.append(tok)
                else:
                    tokens.append(Token(lexeme=lexeme, pattern=last_accept_pat, attr=last_accept_pat))
                i = last_accept_idx
            else:
                # Consome lexema invalido ate proximo separador ou 1 caractere
                err_end = i + 1
                while err_end < n and source_code[err_end] not in self.ignored_chars:
                    err_end += 1
                bad_lex = source_code[i:err_end]
                tokens.append(Token(lexeme=bad_lex, pattern="erro!", attr="erro!"))
                i = err_end

        return tokens
