# Ajuste de seletores do crawler

Este documento registra os seletores CSS usados para identificar ofertas aéreas no HTML coletado.

## Objetivo

Garantir que o parser em `crawler/parser.py` esteja alinhado ao HTML real retornado pelo site.

## Seletores iniciais

O scaffold inicial tenta localizar cards de oferta usando:

```css
[data-testid='flight-card'], .flight-card, .offer-card
```

Dentro de cada card, tenta localizar:

```css
[data-origin], .origin
[data-destination], .destination
[data-price], .price
```

## Próximos passos

1. Capturar um HTML real da página de resultados.
2. Identificar os atributos estáveis dos cards de voo.
3. Atualizar `crawler/parser.py` com seletores definitivos.
4. Criar testes em `tests/` com um fixture HTML salvo localmente.

## Observação

Evite versionar HTMLs com dados sensíveis ou payloads muito grandes. Para amostras, use arquivos pequenos e anonimizados.
