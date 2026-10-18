# Trabalho 06 - Avaliação de Desempenho de Microsserviços com Locust

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white) ![Locust](https://img.shields.io/badge/Locust-2E2E2E?style=for-the-badge&logo=data:image%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCIgdmlld0JveD0iMCAwIDY0IDY0Ij48ZyBmaWxsPSJub25lIiBzdHJva2U9IiNmZmZmZmYiIHN0cm9rZS13aWR0aD0iNCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48ZWxsaXBzZSBjeD0iMzQiIGN5PSIzMSIgcng9IjciIHJ5PSIxMyIgdHJhbnNmb3JtPSJyb3RhdGUoLTI1IDM0IDMxKSIvPjxjaXJjbGUgY3g9IjQzIiBjeT0iMTQiIHI9IjUiLz48cGF0aCBkPSJNNDAgMTAgMzUgNU00NiAxMCA1MSA1TTI4IDI1IDE3IDE4IDEwIDIxTTI4IDMxIDE0IDMyIDggMzlNMzEgNDAgMjIgNTAgMTIgNTFNMzcgMzkgNDQgNDkgNTUgNTNNNDAgMjggNTEgMjUgNTcgMjkiLz48L2c%2BPC9zdmc%2B) ![Docker Compose](https://img.shields.io/badge/Docker%20Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white) ![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white) ![Grafana](https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white) ![Spring Boot](https://img.shields.io/badge/Spring%20Boot-6DB33F?style=for-the-badge&logo=springboot&logoColor=white)

Avaliação de desempenho do sistema distribuído **Spring PetClinic Microservices** utilizando **Locust**, **Docker Compose**, **Prometheus** e **Grafana**. O projeto executa dois perfis de carga — **Leitura** e **Escrita** — sobre diferentes quantidades de usuários, coletando tempo médio de resposta, P95, vazão, total de requisições, taxa de falhas e utilização de CPU dos microsserviços. Projeto acadêmico da disciplina de Sistemas Distribuídos.

## Sumário

- [Como rodar](#como-rodar)
  - [Pré-requisitos](#pré-requisitos)
  - [Rodar a aplicação](#rodar-a-aplicação)
  - [Rodar o experimento completo](#rodar-o-experimento-completo)
  - [Rodar o gerador de gráficos e tabelas](#rodar-o-gerador-de-gráficos-e-tabelas)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Arquitetura](#arquitetura)
- [Descrição do ambiente de execução](#descrição-do-ambiente-de-execução)
- [Metodologia](#metodologia)
- [Análise dos resultados](#análise-dos-resultados)
- [Respostas às questões](#respostas-às-questões)
- [Conclusões](#conclusões)
- [Vídeo demonstrativo](#vídeo-demonstrativo)
- [Licença](#licença)

## Como rodar

### Pré-requisitos

- Docker Desktop em execução;
- Docker Compose disponível;
- Python 3.13 ou compatível;
- Git;
- pelo menos 4 GB de memória disponíveis para os serviços;
- ambiente virtual Python criado em `ads/.venv`.

Instale as dependências do projeto com:

```powershell
.\ads\.venv\Scripts\python.exe -m pip install -r .\ads\requirements.txt
```

### Rodar a aplicação

Entre na pasta da aplicação:

```powershell
Set-Location .\spring-petclinic-microservices
```

Inicie os serviços com Docker Compose:

```powershell
docker compose up -d
```

Verifique o estado dos containers:

```powershell
docker compose ps
```

Interfaces disponíveis:

| Serviço | URL |
|---|---|
| Aplicação/API Gateway | http://localhost:8080 |
| Locust | http://localhost:8089 |
| Grafana | http://localhost:3030 |
| Prometheus | http://localhost:9091 |
| Spring Boot Admin | http://localhost:9090 |

Para encerrar a aplicação:

```powershell
docker compose down
```

### Rodar o experimento completo

Certifique-se de que a aplicação está em execução e volte para a raiz do repositório:

```powershell
Set-Location ..
```

Execute os dois perfis, os três cenários e as 10 repetições por configuração:

```powershell
.\ads\.venv\Scripts\python.exe .\ads\experiments\run_experiments.py `
  --locust-command .\ads\.venv\Scripts\locust.exe
```

O experimento completo possui:

```text
2 perfis × 3 cenários × 10 repetições = 60 execuções
```

Cada execução realiza:

- 1 minuto de aquecimento;
- reinício das estatísticas do Locust;
- 6 minutos de medição;
- coleta de CPU e memória dos containers `customers-service` e `vets-service`.

### Rodar o gerador de gráficos e tabelas

Após a conclusão dos experimentos, execute:

```powershell
.\ads\.venv\Scripts\python.exe .\ads\experiments\generate_results.py
```

As tabelas serão salvas em:

```text
ads/results/processed/
```

Os gráficos serão salvos em:

```text
ads/results/charts/
```

O gerador pode ser executado novamente após novas repetições. Ele processará todos os arquivos brutos disponíveis.

## Estrutura do projeto

```text
.
├── ads/
│   ├── experiments/
│   │   ├── generate_results.py
│   │   └── run_experiments.py
│   ├── grafana-petclinic-dashboard-trabalho06.json
│   ├── locustfile.py
│   ├── requirements.txt
│   └── results/
│       ├── charts/
│       ├── processed/
│       └── raw/
│
├── spring-petclinic-microservices/
├── .gitignore
├── LICENSE
└── README.md
```

Os resultados brutos são separados por execução e incluem arquivos CSV do Locust, amostras do `docker stats`, logs e metadados.

## Arquitetura

O sistema avaliado é composto por microsserviços Spring PetClinic executados em containers Docker:

```text
Locust
   │
   ▼
API Gateway :8080
   ├── Customers Service :8081
   ├── Visits Service   :8082
   └── Vets Service     :8083

Prometheus :9091 ──► métricas Actuator/Prometheus
Grafana    :3030 ──► visualização das métricas
```

O Locust envia as requisições pelo API Gateway. O Prometheus coleta métricas dos serviços e o Grafana permite acompanhar o comportamento da aplicação durante os testes. O script experimental utiliza o `docker stats` para coletar oficialmente a utilização de CPU de dois serviços: `customers-service` e `vets-service`.

## Descrição do ambiente de execução

Preencher antes da entrega final:

| Item | Informação |
|---|---|
| Sistema operacional |  Microsoft Windows 11 Home Single Language |
| Processador | 12th Gen Intel(R) Core(TM) i5-12450H (2.00 GHz) |
| Memória RAM | 16,0 GB (utilizável: 15,7 GB) |
| Versão do Docker | 29.7.2 |
| Versão do Docker Compose | 5.5.1 |
| Versão do Python | 3.13.5 |
| Versão do Locust | 2.46.7 |
| Serviços monitorados | `customers-service` e `vets-service` |
| Limite de memória dos serviços | 512 MB |
| Intervalo do `docker stats` | 5 segundos |

## Metodologia

Foram definidos dois perfis de carga:

| Operação | Perfil Leitura | Perfil Escrita |
|---|---:|---:|
| `GET /api/customer/owners` | 45% | 20% |
| `GET /api/customer/owners/{id}` | 35% | 20% |
| `GET /api/vet/vets` | 15% | 20% |
| `POST /api/customer/owners` | 5% | 40% |

Cada perfil será executado nos seguintes cenários:

| Cenário | Usuários | Aquecimento | Medição |
|---|---:|---:|---:|
| A — Leve | 30 | 1 minuto | 6 minutos |
| B — Moderado | 80 | 1 minuto | 6 minutos |
| C — Elevado | 150 | 1 minuto | 6 minutos |

Cada configuração será repetida 10 vezes, totalizando:

```text
2 perfis × 3 cenários × 10 repetições = 60 execuções
```

Durante o aquecimento, as estatísticas não são utilizadas. Após 1 minuto, uma nova medição do Locust é iniciada com as estatísticas zeradas. Somente os 6 minutos seguintes são salvos nos CSVs oficiais.

As métricas coletadas são:

- tempo médio de resposta, em milissegundos;
- P95 do tempo de resposta, em milissegundos;
- vazão, em requisições por segundo;
- total de requisições;
- taxa de falhas;
- utilização de CPU dos serviços `customers-service` e `vets-service`.

Os resultados são analisados por cenário, perfil e operação. As médias das repetições são geradas pelo script `generate_results.py`.

## Análise dos resultados

> **Seção reservada para preenchimento após a execução das 60 medições.**

### Tabelas

Inserir aqui as tabelas finais geradas em `ads/results/processed/`.

### Gráficos

Inserir aqui os gráficos gerados em `ads/results/charts/`, com a interpretação dos resultados.

### Observações

Registrar tendências, anomalias, limitações e possíveis causas de degradação observadas nos dados.

## Respostas às questões

### 1. Como o aumento de usuários afeta o tempo de resposta?

> Preencher após a análise dos resultados finais.

### 2. Qual perfil apresenta maior vazão?

> Preencher após a análise dos resultados finais.

### 3. Quais operações apresentam maior degradação?

> Preencher após a análise dos resultados finais.

### 4. Como o consumo de CPU varia entre os cenários?

> Preencher após a análise dos resultados finais.

### 5. Qual cenário apresenta maior taxa de falhas?

> Preencher após a análise dos resultados finais.

## Conclusões

> **Seção reservada para preenchimento após a execução das 60 medições.**

Registrar nesta seção:

- o comportamento geral do sistema;
- o perfil mais exigente;
- o cenário de saturação;
- os serviços mais pressionados;
- as principais limitações identificadas;
- a conclusão sobre o desempenho do Spring PetClinic.

## Vídeo demonstrativo

Link do vídeo:

> [Adicionar aqui o link do vídeo demonstrativo com duração entre 4 e 6 minutos.]

## Licença

Este projeto está disponibilizado sob a licença [BSD 3-Clause License](./LICENSE)

Projeto acadêmico da disciplina de Sistemas Distribuídos — UFPI.
