# Google News Scraper

Sistema para coleta em massa de artigos do Google News para treinamento de modelos de IA.

## Estrutura de Arquivos

```
google_news/
├── google_news.py      # Cliente RSS do Google News
├── model.py            # Modelo de dados ArticleModel
├── article_scraper.py  # Extrator de conteúdo com Playwright
├── bulk_scraper.py     # Script principal para coleta em massa
└── articles_soup.py    # Utilitários de parsing (legacy)
```

## Como Funciona

O sistema opera em **duas fases**:

### Fase 1: Coleta de Metadados
- Lê as datas de um arquivo JSON
- Para cada data, executa múltiplas queries no Google News RSS
- Coleta links, títulos, fontes e datas de publicação
- Salva todos os metadados em um arquivo JSON

### Fase 2: Extração de Conteúdo
- Lê os metadados coletados
- Usa Playwright para acessar cada link
- Extrai o conteúdo limpo dos artigos (sem menus, ads, footers)
- Salva um arquivo final com todos os artigos + relatório

## Instalação

```bash
# Instalar dependências
uv add playwright

# Instalar browser
uv run playwright install chromium
```

## Uso Básico

### Executar ambas as fases (padrão)

```bash
uv run python bulk_scraper.py
```

Isso vai:
1. Ler datas de `PETR4.SA_date.json`
2. Coletar metadados → `articles_metadata.json`
3. Extrair conteúdo → `articles.json` + `extraction_report.json`

### Executar apenas Fase 1 (coletar links)

```python
import asyncio
from bulk_scraper import phase1_collect_metadata, load_dates, QUERIES

async def main():
    dates = load_dates('seu_arquivo_datas.json')

    await phase1_collect_metadata(
        dates=dates,
        queries=QUERIES,
        output_file='metadados_saida.json',
        max_concurrent=5,
    )

asyncio.run(main())
```

### Executar apenas Fase 2 (extrair conteúdo)

```python
import asyncio
from bulk_scraper import phase2_extract_content

async def main():
    await phase2_extract_content(
        metadata_file='articles_metadata.json',
        output_file='articles.json',
        report_file='extraction_report.json',
        max_concurrent=15,
        batch_size=100,
    )

asyncio.run(main())
```

## Customização

### Usar arquivo de datas diferente

Crie um arquivo JSON com array de datas ISO 8601:

```json
[
    "2024-01-15 00:00:00-03:00",
    "2024-02-20 00:00:00-03:00",
    "2024-03-10 00:00:00-03:00"
]
```

Depois execute:

```python
import asyncio
from pathlib import Path
from bulk_scraper import phase1_collect_metadata, phase2_extract_content, load_dates, QUERIES

async def main():
    # Configuração - customize os caminhos
    dates_file = Path('/caminho/para/suas_datas.json')
    metadata_file = Path('/caminho/para/metadados.json')
    output_file = Path('/caminho/para/artigos.json')
    report_file = Path('/caminho/para/relatorio.json')

    # Carregar datas
    dates = load_dates(str(dates_file))
    print(f'Carregadas {len(dates)} datas')

    # Fase 1: Coletar metadados
    await phase1_collect_metadata(
        dates=dates,
        queries=QUERIES,
        output_file=str(metadata_file),
        max_concurrent=5,
    )

    # Fase 2: Extrair conteúdo
    await phase2_extract_content(
        metadata_file=str(metadata_file),
        output_file=str(output_file),
        report_file=str(report_file),
        max_concurrent=15,
        batch_size=100,
    )

asyncio.run(main())
```

### Customizar queries de busca

Por padrão, o sistema usa estas queries para maximizar resultados:

```python
QUERIES = [
    'noticia',
    'brasil',
    'economia',
    'politica',
    'mercado',
    'governo',
    'empresa',
    'internacional',
]
```

Para usar queries personalizadas:

```python
from bulk_scraper import phase1_collect_metadata, load_dates

MINHAS_QUERIES = [
    'tecnologia',
    'startup',
    'inovação',
    'inteligência artificial',
]

async def main():
    dates = load_dates('datas.json')

    await phase1_collect_metadata(
        dates=dates,
        queries=MINHAS_QUERIES,  # Suas queries aqui
        output_file='tech_metadata.json',
        max_concurrent=5,
    )
```

## Arquivos de Saída

| Arquivo | Descrição |
|---------|-----------|
| `articles_metadata.json` | Links coletados (Fase 1) |
| `articles.json` | Artigos com conteúdo extraído (Fase 2) |
| `extraction_report.json` | Relatório da extração |

### Metadados (articles_metadata.json)

```json
[
  {
    "title": "Título da notícia",
    "link": "https://news.google.com/rss/articles/...",
    "pub_date": "2024-01-15T10:30:00",
    "source_name": "G1",
    "source_url": "https://g1.globo.com",
    "query": "noticia",
    "search_date": "2024-01-15"
  }
]
```

### Artigos extraídos (articles.json)

```json
[
  {
    "title": "Título da notícia",
    "content": "Conteúdo completo do artigo...",
    "url": "https://site-real.com/noticia",
    "original_url": "https://news.google.com/rss/articles/...",
    "pub_date": "2024-01-15T10:30:00",
    "source": {
      "name": "G1",
      "url": "https://g1.globo.com"
    },
    "fetch_date": "2024-01-20T15:30:00"
  }
]
```

### Relatório (extraction_report.json)

```json
{
  "summary": {
    "total_metadata": 19199,
    "total_extracted": 15000,
    "success_rate": "78.1%",
    "extraction_time": "4:30:00",
    "start_time": "2024-01-20T10:00:00",
    "end_time": "2024-01-20T14:30:00"
  },
  "by_date": {
    "metadata_count": {"2024-01-15": 250, ...},
    "extracted_count": {"2024-01-15": 200, ...}
  },
  "by_source": {
    "G1": 1500,
    "Folha": 1200,
    ...
  },
  "queries_used": ["noticia", "brasil", "economia", ...]
}
```

## Parâmetros de Performance

| Parâmetro | Descrição | Padrão | Recomendação |
|-----------|-----------|--------|--------------|
| `max_concurrent` (Fase 1) | Datas processadas em paralelo | 5 | 5-10 |
| `max_concurrent` (Fase 2) | Artigos extraídos em paralelo | 10 | 10-20 |
| `batch_size` | Artigos processados por vez | 50 | 50-100 |

## Estimativas de Tempo

| Quantidade | Fase 1 | Fase 2 |
|------------|--------|--------|
| 10 datas | ~20s | ~5 min |
| 67 datas | ~1.5 min | ~4.5 horas |
| 100 datas | ~2 min | ~7 horas |

## Dicas

1. **Execute a Fase 2 em background** - demora várias horas para milhares de artigos
2. **Pular Fase 1** - se `articles_metadata.json` já existe, a Fase 1 é pulada automaticamente
3. **Deduplicação** - links duplicados são automaticamente removidos
4. **Conteúdo limpo** - o extrator remove menus, ads, footers e elementos de navegação
