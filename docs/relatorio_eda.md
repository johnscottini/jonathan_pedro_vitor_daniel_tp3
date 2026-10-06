# Relatório de EDA — Customer Support Ticket Dataset

Documento autocontido: reúne o que a análise exploratória do
[`eda/eda.ipynb`](../eda/eda.ipynb) mostrou e o que isso implica para o modelo de
classificação de intenção. Os números citados vêm das saídas do notebook.

---

## 1. Problema

Uma equipe de atendimento recebe tickets de suporte por quatro canais (email,
telefone, chat e redes sociais). Hoje, alguém precisa ler cada ticket para
decidir para qual fila ele vai e com que urgência. Isso custa tempo no momento
mais sensível do atendimento: a chegada.

O objetivo do projeto é automatizar essa triagem. Dado o texto escrito pelo
cliente, o sistema deve prever a **intenção** por trás do ticket — pedido de
reembolso, problema técnico, cancelamento, dúvida sobre cobrança ou consulta
sobre produto — e devolver essa classificação por uma API.

A decisão que esta análise apoia é anterior ao modelo: **esses dados sustentam
um classificador de intenção? Qual coluna serve de alvo, quais campos podem
virar features e que desempenho é realista esperar?**

---

## 2. Dados

| Item | Valor |
|---|---|
| Fonte | [Customer Support Ticket Dataset](https://www.kaggle.com/datasets/suraj520/customer-support-ticket-dataset/data) (Kaggle, autor `suraj520`) |
| Licença | CC0 — domínio público |
| Volume | 8.469 tickets × 17 colunas |
| Natureza | **Sintético** (gerado programaticamente, não são tickets reais) |

As 17 colunas se dividem em cinco naturezas: duas **numéricas** (`Customer Age`,
`Customer Satisfaction Rating`), sete **categóricas** (`Ticket Type`,
`Ticket Subject`, `Ticket Status`, `Ticket Priority`, `Ticket Channel`,
`Customer Gender`, `Product Purchased`), duas **textuais** (`Ticket Description`,
`Resolution`), três **temporais** (`Date of Purchase`, `First Response Time`,
`Time to Resolution`) e três de **identificação ou dado pessoal** (`Ticket ID`,
`Customer Name`, `Customer Email`).

**Qualidade dos dados.** Não há linhas duplicadas, `Ticket ID` repetido,
categorias escritas de formas diferentes, espaços extras ou textos vazios — as
categorias chegam padronizadas. Três problemas relevantes foram encontrados:

1. **Nulos estruturais, não erros.** `Resolution`, `Time to Resolution` e
   `Customer Satisfaction Rating` têm exatamente 5.700 nulos cada, e são nulos em
   100% dos tickets que não estão `Closed`. São colunas de desfecho: só existem
   depois que o ticket é resolvido. A limpeza **preservou** esses nulos —
   imputá-los inventaria uma resolução que não houve.
2. **Bug de template.** 100% das descrições contêm o placeholder literal
   `{product_purchased}`, nunca substituído pelo nome do produto, além de frases
   genéricas repetidas ("Please assist.").
3. **Inconsistência temporal.** Parte dos tickets fechados tem
   `Time to Resolution` **anterior** a `First Response Time`, o que é impossível
   em um fluxo real. Os timestamps foram sorteados sem respeitar ordem causal e,
   por isso, não sustentam nenhum cálculo de SLA.

Nenhuma linha foi removida. A preparação se limitou a conversões de tipo e a
colunas derivadas (`description_length`, `is_closed`, `purchase_year`,
`purchase_month`, prioridade codificada como ordinal).

---

## 3. Análise

### 3.1 Univariada

Todas as variáveis categóricas têm distribuição quase uniforme, sem categoria
dominante e sem cauda longa: as cinco intenções ficam entre 19,29% e 20,69%; os
16 assuntos, entre 5,64% e 6,80%; os quatro canais e as quatro prioridades giram
em torno de 25%; nenhum dos 42 produtos passa de 2,83%. As numéricas têm média e
mediana praticamente coincidentes (idade ≈ 44, satisfação ≈ 3), sinal de
distribuições simétricas, sem assimetria nem outliers.

### 3.2 Correlação

A matriz de correlação de Spearman entre as oito variáveis numéricas (originais e
derivadas) é praticamente branca. As duas únicas correlações fortes —
`horas_ate_primeira_resposta` com `ano_compra` (0,87) e com `mes_compra` (0,51) —
são artefato de construção: a duração foi calculada a partir da data da compra e
herda a variação dela. Descontados esses pares, **a maior correlação do conjunto
é 0,04**.

Spearman em vez de Pearson porque parte das variáveis é ordinal (satisfação,
prioridade) ou binária, e Spearman mede relação monotônica sem exigir escala de
intervalo nem normalidade.

### 3.3 Teste de hipótese formal

A hipótese **H2**, formulada no TP1, propunha que as intenções se organizam em
dois eixos — "algo está quebrado" (técnico) e "algo na conta/pedido precisa
mudar" (comercial) — e que esse agrupamento serviria de base para um
classificador hierárquico.

| | |
|---|---|
| H₀ | A distribuição da satisfação é a mesma nos dois eixos |
| H₁ | As distribuições diferem |
| Teste | Mann-Whitney U, bilateral, α = 0,05 |
| Amostra | 2.769 tickets `Closed` (1.752 técnicos, 1.017 comerciais) |
| Resultado | U = 897.311,5 · **p = 0,7467** · rank-biserial = −0,007 |

Mann-Whitney e não t-test porque a satisfação é uma nota **ordinal** de 1 a 5: o
t-test pressupõe normalidade e trataria a distância entre as notas 1 e 2 como
igual à distância entre 4 e 5. Mann-Whitney compara postos, que é o que uma
escala ordinal permite.

**O que o p-valor de 0,75 quer dizer.** Se não houvesse diferença nenhuma entre
os dois grupos, ainda assim haveria 75% de chance de observar uma diferença deste
tamanho só por sorteio. Sendo muito maior que os 5% adotados como limite, **não
rejeitamos H₀**. O tamanho de efeito confirma por outro caminho: pegando um
ticket técnico e um comercial ao acaso, a chance de o técnico ter nota maior é de
49,6% — o mesmo que jogar uma moeda.

Não rejeitar H₀ não prova que os grupos são iguais; prova que, com estes dados,
não há evidência de diferença. **A H2 do TP1 não se sustenta**, e o caminho do
classificador hierárquico fica descartado como atalho.

### 3.4 Demais hipóteses do TP1

| Hipótese do TP1 | Teste | p | Veredito |
|---|---|---|---|
| **H1** — distribuição de intenções artificialmente uniforme | Qui-quadrado de aderência | 0,1149 | **Sustentada** |
| **H2** — intenções se agrupam em eixo técnico e comercial | Mann-Whitney | 0,7467 | **Não sustentada** |
| **H3** — `Ticket Type` e `Ticket Subject` são rótulos independentes | Qui-quadrado de independência | 0,9807 | **Sustentada** |
| **H4** — metadados e tamanho do texto não informam a intenção | Qui-quadrado (canal, prioridade, gênero) e Kruskal-Wallis (tamanho do texto) | 0,46 / 0,56 / 0,66 / 0,47 | **Sustentada** |

---

## 4. Insights principais

**I1 — Os dois campos de rótulo se contradizem.** `Ticket Type` e
`Ticket Subject` são estatisticamente independentes (p = 0,98): cada um dos 16
assuntos aparece sob os 5 tipos em proporções próximas de 20%. Existem tickets
com assunto *Refund request* classificados como tipo *Technical issue*. Não é uma
hierarquia, são dois rótulos sorteados separadamente.

**I2 — Nenhum metadado prevê a intenção.** Canal, prioridade, gênero e tamanho
da descrição são todos independentes do tipo do ticket (p entre 0,46 e 0,66).
Não existe feature barata: não dá para acertar a intenção olhando por onde o
ticket entrou ou que prioridade recebeu.

**I3 — As intenções são artificialmente equilibradas.** As cinco classes são
compatíveis com uma distribuição uniforme (p = 0,11), ao contrário de uma
operação real, em que problemas técnicos e cobrança costumam dominar.

**I4 — O texto livre é parcialmente boilerplate.** 100% das descrições contêm o
placeholder `{product_purchased}` e frases de template repetidas. O sinal
aproveitável está no trecho específico de cada ticket, não no texto inteiro.

**I5 — As colunas de desfecho são armadilha de vazamento.** `Resolution`,
`Time to Resolution` e `Customer Satisfaction Rating` só existem para tickets já
fechados. Usá-las como feature produziria um modelo com desempenho excelente na
validação e inútil em produção, porque no momento da predição elas não existem.

---

## 5. Limitações

1. **O dataset é sintético e isso contamina toda conclusão sobre desempenho.**
   As variáveis foram geradas independentemente umas das outras, e é por isso que
   quase todo teste estatístico dá "sem associação". Um modelo treinado aqui não
   tem como ser avaliado de forma transferível para dados reais.
2. **Os rótulos são inconsistentes entre si** (I1), então parte do "erro" de
   qualquer classificador será ruído de rotulagem, não falha do modelo.
3. **Os timestamps não respeitam ordem causal**, o que inviabiliza qualquer
   análise de SLA, tempo de resposta ou produtividade.
4. **A satisfação só existe para 2.769 dos 8.469 tickets** (32,7%), e essa
   amostra não é aleatória: é exatamente o subconjunto dos tickets fechados.
5. **Não há informação temporal confiável de chegada dos tickets**, o que impede
   analisar sazonalidade ou deriva de distribuição ao longo do tempo.

---

## 6. Próximos passos — a pergunta de classificação do TP3

### A pergunta

> **Dado o texto livre de um ticket recém-aberto, qual é a intenção do cliente?**

É uma classificação multiclasse supervisionada, com uma restrição que a análise
tornou explícita: no instante da predição existe apenas o texto do cliente e
alguns metadados de entrada — nada de desfecho.

### A decisão que este relatório obriga: qual é o alvo

O insight **I1** não deixa alternativa. Como `Ticket Type` e `Ticket Subject` são
independentes, não dá para prever os dois nem tratá-los como hierarquia. O TP3
precisa escolher um, e a escolha recomendada é **`Ticket Type`**, por três
motivos: tem 5 classes em vez de 16 (mais exemplos por classe); corresponde ao
roteamento por fila de atendimento, que é a decisão de negócio real; e mantém a
tarefa comparável ao que a API já devolve hoje no `/predict`.

A consequência de I1 precisa ser dita abertamente no TP3: como os rótulos são
inconsistentes, existe um **teto de acurácia** que nenhum modelo ultrapassa neste
dataset, por melhor que seja.

### Features permitidas e proibidas

| Permitidas | Proibidas (vazamento — ver I5) |
|---|---|
| `Ticket Description` (feature principal) | `Resolution` |
| `Product Purchased`, `Ticket Channel`, `Ticket Priority` | `Time to Resolution` |
| `Customer Age` | `Customer Satisfaction Rating` |
| | `Ticket Status` (só existe após a triagem) |

Pelo insight **I2**, os metadados permitidos provavelmente não vão agregar nada —
mas vale medir, em vez de assumir.

### Baseline, métrica e expectativa

- **Baseline obrigatório:** classificador que sempre responde a classe mais
  frequente. Pelo insight **I3**, ele acerta ~20,7%. Qualquer modelo precisa
  superar isso com folga para justificar existir.
- **Modelo inicial:** TF-IDF sobre a descrição + regressão logística. Simples,
  rápido e interpretável — permite inspecionar quais palavras pesam em cada
  classe, o que é mais informativo aqui do que ganhar alguns pontos com um modelo
  opaco.
- **Pré-processamento:** remover o placeholder `{product_purchased}` e as frases
  de template (insight **I4**) antes de vetorizar, para o modelo não aprender
  ruído comum a todas as classes.
- **Métrica:** **F1 macro**, não acurácia. As classes são balanceadas neste
  dataset (I3), mas em produção não serão, e o F1 macro já força o modelo a ser
  avaliado classe a classe. Reportar também a matriz de confusão.
- **Expectativa realista:** desempenho modesto, próximo do baseline. Dado I1 e
  I2, o resultado honesto deste dataset provavelmente é "o texto quase não prevê
  o rótulo" — e documentar isso, com evidência, vale mais do que forçar um número
  bonito.

### Integração com a API

O `POST /predict` hoje devolve uma intenção simulada por correspondência de
palavras-chave. No TP3 ele passa a carregar o modelo treinado e devolver a classe
prevista com a probabilidade associada, mantendo o mesmo contrato de entrada e
saída (`PredictRequest` / `PredictResponse`) — a troca fica invisível para quem
consome a API.
