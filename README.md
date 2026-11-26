# GALS-INE5421 — Gerador de Analisadores Léxicos e Sintáticos (SLR)

Reestruturação modular do arcabouço para os **Trabalhos 1 e 2** de Linguagens Formais e Compiladores (INE5421), com Tabela de Símbolos compartilhada e execução isolada ou integrada.

## Estrutura do Repositório

- `src/common/symbol_table.py`: Tabela de Símbolos (`SymbolTable`) com pré-carga de palavras reservadas (`PR`), resolução `⟨lexema, PR⟩` e endereços para identificadores e constantes.
- `src/lexer/lexer_framework.py`:
  - Conversão direta de ER para AFD (algoritmo de Aho: árvore sintática, `nullable`, `firstpos`, `lastpos`, `followpos`).
  - Minimização de AFD.
  - União de AFDs via transição `&` ($epsilon$).
  - Determinização do AFND resultante (tabela léxica implícita).
  - Visualização em tabela dos autômatos e da tabela léxica, além da tokenização com detecção de `⟨lexema, erro!⟩`.
- `src/parser/slr_framework.py`:
  - Leitura de GLC no formato `⟨Não terminal⟩ ::= corpo` com literais entre `""` e `&`.
  - Algoritmos `First` e `Follow`, `Closure`, `Coleção Canônica`, construção da tabela `SLR` e `LR Parsing` (pilha de execução).
- `examples/lang_demo/`: Definições regulares, palavras reservadas, gramática GLC, programa válido e programa inválido.
- `main.py`: CLI para executar o léxico isolado (`lex`) ou o compilador integrado (`compilar`).

## Como Executar (HowTo)

### 1. Testar apenas o Analisador Léxico (Trabalho 1)

```bash
python -m src.main lex --er examples/lang_demo/definicoes.er --fonte examples/lang_demo/fonte_valido.ilha --tabelas
```

### 2. Testar Léxico + Tabela de Símbolos + Sintático SLR (Trabalho 1 + 2)

```bash
python -m src.main compilar --er examples/lang_demo/definicoes.er --glc examples/lang_demo/gramatica.glc --pr examples/lang_demo/palavras_reservadas.txt --fonte examples/lang_demo/fonte_valido.ilha
```

O comando integrado grava a lista de tokens em `out/tokens.txt` e a pilha de execução em
`out/pilha_execucao.txt`. Para verificar uma rejeição sintática, substitua a fonte por
`examples/lang_demo/fonte_invalido.ilha`; o comando termina com código 1 após registrar a pilha.

Os símbolos são exibidos literalmente, por exemplo `⟨{, {⟩`, `⟨=, =⟩` e `⟨;, ;⟩`.
Identificadores e constantes exibem seu endereço na tabela de símbolos, como `⟨id, 4⟩`
e `⟨num, 5⟩`.

## Linguagem de demonstração

`examples/lang_demo/` contém uma linguagem pequena para declarações, atribuições, soma de
inteiros e `escreva`. As definições regulares incluem todos os delimitadores usados pela GLC,
e as palavras reservadas são carregadas antes da análise léxica.

## Autores

Lucas Semprebon Herdt, Pedro Silva Chaves e Yano H. de Melo R. Cavalcante.

INE5421 - Linguagens Formais e Compiladores, Profa. Jerusa Marchi.
