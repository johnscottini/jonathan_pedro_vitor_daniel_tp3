# Planejamento TP3 — modelo de classificação e teste adversarial

Documento de planejamento da próxima etapa do projeto (`planejamento_tp3`). Ele
fixa três decisões: o algoritmo que vai prever a intenção das mensagens, a forma
de transformar o texto em atributos numéricos e o alvo autorizado para o pentest
do TP4/TP5.

**Problema (formalizado na seção 9 do [`eda/eda_tp3.ipynb`](../eda/eda_tp3.ipynb)):**
dado o texto de uma mensagem de atendimento ao cliente, qual é a intenção do
usuário?

- **X:** `Ticket Description`, sem o placeholder `{product_purchased}`.
- **y:** `Ticket Type`, com 5 classes balanceadas (19,3% a 20,7% cada).
- **Baseline:** prever sempre a classe majoritária dá 20,7% de acurácia.

---

## 1. Modelo candidato

**Principal: Regressão Logística multiclasse** (`sklearn.linear_model.LogisticRegression`,
multinomial). **Comparação: SVM linear** (`sklearn.svm.LinearSVC`).

Por que a Regressão Logística é adequada para este problema:

- **Funciona bem com texto vetorizado.** O `CountVectorizer` gera milhares de
  colunas, quase todas zero em cada mensagem (matriz esparsa). Modelos lineares
  treinam rápido nesse formato e generalizam bem com regularização (`C`), mesmo
  com ~8,5 mil exemplos.
- **Devolve probabilidade por classe.** É o que o `POST /predict` já expõe
  (`intent` + `confidence`), então o modelo entra na API sem mudar o contrato.
- **É interpretável.** Cada palavra tem um peso por classe. Dá para listar os
  termos que mais puxam para "Refund request" ou "Technical issue" e conferir se
  o modelo aprendeu algo do texto ou ruído dos templates do dataset (insight I4).
- **Serve como linha de base honesta.** A EDA mostrou que o dataset é sintético e
  que os rótulos são pouco consistentes (H3, I1). Antes de testar modelos mais
  complexos, é preciso saber quanto um modelo simples consegue superar os 20,7%.

O **LinearSVC** entra como comparação: costuma ser forte em classificação de
texto esparso, mas não devolve probabilidade diretamente (exigiria calibração).
Fica com o modelo que tiver melhor **F1 macro** na validação cruzada.

**Avaliação planejada:** treino/teste estratificado 80/20, validação cruzada de
5 folds para os hiperparâmetros, F1 macro como métrica principal, além de
acurácia, matriz de confusão e o relatório por classe.

## 2. Estratégia de representação do texto: `CountVectorizer`

O texto será transformado em atributos com o **`CountVectorizer`**
(`sklearn.feature_extraction.text`): cada mensagem vira um vetor com a contagem
de cada termo do vocabulário (*bag-of-words*).

Por que essa escolha:

- **É simples e transparente.** Cada coluna é uma palavra (ou um par de
  palavras), e o valor é quantas vezes ela aparece. Isso combina com a
  interpretabilidade da Regressão Logística: o peso aprendido pertence a um termo
  legível.
- **Captura o sinal que importa aqui.** A intenção aparece em palavras-chave
  ("refund", "cancel", "charged", "not working"). A contagem de termos já
  representa esse sinal, sem exigir embeddings ou modelos pré-treinados.
- **Dá controle sobre o vocabulário**, e isso é necessário neste dataset:
  - `stop_words="english"` remove palavras sem conteúdo;
  - `ngram_range=(1, 2)` mantém expressões como "not working" e "money back";
  - `min_df` descarta termos raros, reduzindo ruído e dimensão;
  - o pré-processamento remove o placeholder `{product_purchased}` e as frases
    de template repetidas em todas as classes (I4), que só adicionariam ruído
    comum.
- **Vai num `Pipeline` com o classificador.** O vocabulário é aprendido só nos
  dados de treino, o que evita vazamento do conjunto de teste, e o pipeline
  inteiro pode ser serializado e carregado pela API.

## 3. Alvo para o teste adversarial (TP4/TP5)

A API roda na máquina da equipe e fica acessível pela internet por um
**Cloudflare Tunnel**: o `cloudflared` abre uma conexão de saída até a
Cloudflare, que publica uma URL HTTPS e encaminha as requisições para o
`localhost:8000`. Não é preciso abrir portas no roteador nem contratar
hospedagem.

| Item | Valor |
|---|---|
| **Alvo autorizado (URL pública)** | **https://guest-pepper-very-hopkins.trycloudflare.com** |
| Documentação do alvo | https://guest-pepper-very-hopkins.trycloudflare.com/docs e `/openapi.json` |
| Origem | API FastAPI da equipe em `http://localhost:8000` (`uvicorn main:app --no-server-header`, a partir de `fastapi/`) |
| Escopo | `/auth/token`, `/predict`, `/predictions`, `/predictions/{id}`, `/tickets`, `/tickets/{id}`, `/health`, `/docs` |
| Fora do escopo | Qualquer outro host, serviço ou porta da máquina; ataques de negação de serviço volumétricos |
| Contas de teste | `alice`, `bob` e `admin`, criadas por `fastapi/sqlite_database.py` (senhas no README) |

Como reproduzir o túnel, com a API já rodando:

```bash
cloudflared tunnel --url http://localhost:8000
```

> **Atenção:** a URL acima é de um *quick tunnel*, gerado sem conta na
> Cloudflare. Ela só responde enquanto a API e o `cloudflared` estão rodando, e
> **muda a cada execução**. Para o ataque do TP4, a equipe sobe os dois
> processos durante a janela combinada com a equipe adversária e envia a URL
> gerada naquele momento.
