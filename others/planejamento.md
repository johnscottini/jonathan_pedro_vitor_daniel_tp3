# Planejamento TP3 — modelo de classificação e teste adversarial

Problema (seção 11 do [`eda/eda_tp3.ipynb`](../eda/eda_tp3.ipynb)): dado o texto
de uma mensagem de atendimento ao cliente, qual é a intenção do usuário?
X = `Ticket Description`; y = `Ticket Type` (5 classes balanceadas). O baseline
da classe majoritária acerta 20,7%.

## 1. Modelo candidato

Regressão Logística multiclasse, com SVM linear (`LinearSVC`) como comparação.

A Regressão Logística é adequada porque:

- funciona bem com texto vetorizado, que gera muitas colunas esparsas;
- devolve a probabilidade de cada classe, que é o formato do `/predict`
  (`intent` e `confidence`);
- é interpretável: os pesos mostram quais palavras indicam cada intenção.

A avaliação usará validação cruzada estratificada, com F1 macro como métrica
principal e matriz de confusão.

## 2. Representação do texto: `CountVectorizer`

O `CountVectorizer` transforma cada mensagem num vetor com a contagem de cada
termo do vocabulário. Foi escolhido porque:

- a intenção aparece em palavras-chave ("refund", "cancel", "charged"), e a
  contagem de termos já captura esse sinal;
- cada coluna é uma palavra, o que mantém o modelo interpretável;
- permite remover stop words e termos raros (`stop_words`, `min_df`) e as
  frases de template identificadas no EDA (seção 7.7);
- é ajustado só nos dados de treino dentro de um `Pipeline`, sem vazamento para
  o teste.

## 3. Alvo para o teste adversarial (TP4/TP5)

A API roda localmente e é publicada pelo Cloudflare Tunnel
(`cloudflared tunnel --url http://localhost:8000`).

| Item | Valor |
|---|---|
| URL da API (alvo autorizado) | https://guest-pepper-very-hopkins.trycloudflare.com |
| Documentação | https://guest-pepper-very-hopkins.trycloudflare.com/docs |
| Escopo | `/auth/token`, `/predict`, `/predictions`, `/predictions/{id}`, `/tickets`, `/tickets/{id}`, `/health`, `/docs` |
| Fora do escopo | Outros serviços da máquina e ataques de negação de serviço volumétricos |
| Contas de teste | `alice`, `bob` e `admin` (senhas no README) |
