# CNPJ.ws — Consultando CNPJ na API Pública

> Fonte oficial: https://docs.cnpj.ws/referencia-de-api/api-publica/consultando-cnpj  
> Consultado em: 2026-09-16  
> Objetivo: contexto técnico para desenvolvimento, agentes de IA e RAG.
>
> Observação: síntese técnica reestruturada da documentação oficial.

## 1. Objetivo

Consultar os dados de uma empresa na base pública do CNPJ.ws a partir de um CNPJ.

A documentação informa que a consulta é feita **na base de dados do próprio CNPJ.ws**.

## 2. Endpoint

### Método

```http
GET
```

### URL

```text
https://publica.cnpj.ws/cnpj/{cnpj}
```

Onde `{cnpj}` representa o CNPJ **sem caracteres especiais**.

Exemplo de estrutura:

```text
https://publica.cnpj.ws/cnpj/00000000000000
```

## 3. Parâmetro de caminho

| Campo | Local | Tipo documentado | Obrigatório | Descrição |
|---|---|---:|---:|---|
| `cnpj` | path | `integer` na referência interativa | sim | Número do CNPJ a consultar, sem máscara |

### Recomendação de implementação

Mesmo que a interface da documentação apresente o parâmetro como `integer`, é mais seguro tratá-lo como **string de 14 dígitos** na aplicação cliente para preservar zeros à esquerda e evitar limitações numéricas de alguma linguagem.

Normalização sugerida:

```text
"12.345.678/0001-90" -> "12345678000190"
```

## 4. Limite de chamadas

A API pública permite **até 3 consultas por minuto por IP**.

Esse limite deve ser considerado parte do contrato operacional do endpoint.

## 5. Respostas HTTP documentadas

| Status | Significado prático |
|---:|---|
| `200` | Consulta realizada e registro retornado |
| `404` | Registro solicitado não encontrado ou recurso correspondente inexistente |
| `429` | Limite de requisições excedido |

## 6. Schema da resposta `200`

A resposta principal é um objeto JSON com informações da empresa e do estabelecimento consultado.

### 6.1. Empresa

```text
Empresa
├── cnpj_raiz: string
├── razao_social: string
├── capital_social: string
├── responsavel_federativo: string
├── atualizado_em: datetime/string
├── porte: Porte
├── natureza_juridica: NaturezaJuridica
├── qualificacao_do_responsavel: Qualificacao
├── socios: Socio[]
├── simples: Simples | null
└── estabelecimento: Estabelecimento
```

### Campos de nível superior

| Campo | Tipo | Descrição funcional |
|---|---|---|
| `cnpj_raiz` | string | Oito primeiros dígitos que identificam a raiz empresarial |
| `razao_social` | string | Razão social da empresa |
| `capital_social` | string | Capital social, documentado como string |
| `responsavel_federativo` | string | Informação de responsável federativo quando aplicável |
| `atualizado_em` | datetime/string | Momento de atualização do registro na base |
| `porte` | object | Porte empresarial |
| `natureza_juridica` | object | Natureza jurídica |
| `qualificacao_do_responsavel` | object | Qualificação do responsável |
| `socios` | array | Quadro de sócios/administradores retornado |
| `simples` | object ou null | Informações de Simples Nacional/MEI |
| `estabelecimento` | object | Dados cadastrais do estabelecimento consultado |

## 7. Objetos auxiliares

### 7.1. Porte

```json
{
  "id": "string",
  "descricao": "string"
}
```

### 7.2. Natureza jurídica

```json
{
  "id": "string",
  "descricao": "string"
}
```

### 7.3. Qualificação

```json
{
  "id": 0,
  "descricao": "string"
}
```

## 8. Sócios

Cada item de `socios` possui, segundo o schema documentado:

| Campo | Tipo aproximado | Observação |
|---|---|---|
| `cpf_cnpj_socio` | string | Documento pode aparecer mascarado |
| `nome` | string | Nome do sócio |
| `tipo` | string | Tipo de pessoa |
| `data_entrada` | date/string | Data de entrada |
| `cpf_representante_legal` | string | CPF do representante, podendo vir mascarado |
| `nome_representante` | string ou null | Nome do representante legal |
| `faixa_etaria` | string | Faixa etária |
| `atualizado_em` | datetime/string | Atualização do registro |
| `pais_id` | string | Identificador de país |
| `qualificacao_socio` | object | Código e descrição da qualificação |
| `qualificacao_representante` | string ou null | Qualificação do representante |
| `pais` | object, quando presente | Informações do país relacionado |

### Objeto `pais`

```json
{
  "id": "string",
  "iso2": "string",
  "iso3": "string",
  "nome": "string",
  "comex_id": "string"
}
```

## 9. Simples Nacional e MEI

O campo `simples` pode ser `null`.

Quando presente, o schema documentado contém:

| Campo | Tipo aproximado |
|---|---|
| `simples` | string |
| `data_opcao_simples` | date/string |
| `data_exclusao_simples` | date/string |
| `mei` | string |
| `data_opcao_mei` | date/string |
| `data_exclusao_mei` | date/string |
| `atualizado_em` | datetime/string |

Estrutura:

```json
{
  "simples": "string",
  "data_opcao_simples": "YYYY-MM-DD",
  "data_exclusao_simples": "YYYY-MM-DD",
  "mei": "string",
  "data_opcao_mei": "YYYY-MM-DD",
  "data_exclusao_mei": "YYYY-MM-DD",
  "atualizado_em": "ISO-8601"
}
```

Campos de data devem ser tratados como potencialmente nulos em integrações defensivas.

## 10. Estabelecimento

O objeto `estabelecimento` concentra os dados do CNPJ específico consultado.

### Campos cadastrais

| Campo | Tipo aproximado |
|---|---|
| `cnpj` | string |
| `cnpj_raiz` | string |
| `cnpj_ordem` | string |
| `cnpj_digito_verificador` | string |
| `tipo` | string |
| `nome_fantasia` | string ou null |
| `situacao_cadastral` | string |
| `data_situacao_cadastral` | date/string |
| `data_inicio_atividade` | date/string |
| `nome_cidade_exterior` | string ou null |
| `situacao_especial` | string ou null |
| `data_situacao_especial` | date/string ou null |
| `atualizado_em` | datetime/string |

### Endereço

| Campo | Tipo aproximado |
|---|---|
| `tipo_logradouro` | string |
| `logradouro` | string |
| `numero` | string |
| `complemento` | string ou null |
| `bairro` | string |
| `cep` | string |

### Contato

| Campo | Tipo aproximado |
|---|---|
| `ddd1` | string |
| `telefone1` | string |
| `ddd2` | string |
| `telefone2` | string |
| `ddd_fax` | string |
| `fax` | string |
| `email` | string ou null |

## 11. CNAE / atividades econômicas

O estabelecimento contém:

- `atividade_principal`: um objeto CNAE;
- `atividades_secundarias`: uma lista de objetos CNAE.

Schema documentado de atividade:

```json
{
  "id": "string",
  "secao": "string",
  "divisao": "string",
  "grupo": "string",
  "classe": "string",
  "subclasse": "string",
  "descricao": "string"
}
```

## 12. Localização

### País

```json
{
  "id": "string",
  "iso2": "string",
  "iso3": "string",
  "nome": "string",
  "comex_id": "string"
}
```

### Estado

```json
{
  "id": 0,
  "nome": "string",
  "sigla": "string",
  "ibge_id": 0
}
```

### Cidade

```json
{
  "id": 0,
  "nome": "string",
  "ibge_id": 0,
  "siafi_id": "string"
}
```

## 13. Situação cadastral

O estabelecimento também pode trazer:

```text
motivo_situacao_cadastral
```

O exemplo da documentação mostra que esse campo pode ser `null`.

## 14. Inscrições estaduais

`inscricoes_estaduais` é uma lista.

Schema:

```json
{
  "inscricao_estadual": "string",
  "ativo": true,
  "atualizado_em": "ISO-8601",
  "estado": {
    "id": 0,
    "nome": "string",
    "sigla": "string",
    "ibge_id": 0
  }
}
```

## 15. Estrutura consolidada da resposta

Schema de referência simplificado:

```json
{
  "cnpj_raiz": "string",
  "razao_social": "string",
  "capital_social": "string",
  "responsavel_federativo": "string",
  "atualizado_em": "ISO-8601",
  "porte": {
    "id": "string",
    "descricao": "string"
  },
  "natureza_juridica": {
    "id": "string",
    "descricao": "string"
  },
  "qualificacao_do_responsavel": {
    "id": 0,
    "descricao": "string"
  },
  "socios": [
    {
      "cpf_cnpj_socio": "string",
      "nome": "string",
      "tipo": "string",
      "data_entrada": "YYYY-MM-DD",
      "cpf_representante_legal": "string",
      "nome_representante": null,
      "faixa_etaria": "string",
      "atualizado_em": "ISO-8601",
      "pais_id": "string",
      "qualificacao_socio": {
        "id": 0,
        "descricao": "string"
      },
      "qualificacao_representante": null,
      "pais": {
        "id": "string",
        "iso2": "string",
        "iso3": "string",
        "nome": "string",
        "comex_id": "string"
      }
    }
  ],
  "simples": null,
  "estabelecimento": {
    "cnpj": "string",
    "atividades_secundarias": [],
    "cnpj_raiz": "string",
    "cnpj_ordem": "string",
    "cnpj_digito_verificador": "string",
    "tipo": "string",
    "nome_fantasia": "string",
    "situacao_cadastral": "string",
    "data_situacao_cadastral": "YYYY-MM-DD",
    "data_inicio_atividade": "YYYY-MM-DD",
    "nome_cidade_exterior": null,
    "tipo_logradouro": "string",
    "logradouro": "string",
    "numero": "string",
    "complemento": null,
    "bairro": "string",
    "cep": "string",
    "ddd1": "string",
    "telefone1": "string",
    "ddd2": "string",
    "telefone2": "string",
    "ddd_fax": "string",
    "fax": "string",
    "email": null,
    "situacao_especial": null,
    "data_situacao_especial": null,
    "atualizado_em": "ISO-8601",
    "atividade_principal": {
      "id": "string",
      "secao": "string",
      "divisao": "string",
      "grupo": "string",
      "classe": "string",
      "subclasse": "string",
      "descricao": "string"
    },
    "pais": {
      "id": "string",
      "iso2": "string",
      "iso3": "string",
      "nome": "string",
      "comex_id": "string"
    },
    "estado": {
      "id": 0,
      "nome": "string",
      "sigla": "string",
      "ibge_id": 0
    },
    "cidade": {
      "id": 0,
      "nome": "string",
      "ibge_id": 0,
      "siafi_id": "string"
    },
    "motivo_situacao_cadastral": null,
    "inscricoes_estaduais": []
  }
}
```

## 16. Erros

A documentação apresenta um schema genérico para respostas de erro como `404` e `429`:

```json
{
  "status": 0,
  "titulo": "string",
  "detalhes": "string",
  "validacao": [
    "string"
  ]
}
```

### `404`

Trate como consulta não atendida por inexistência/não localização do recurso solicitado.

Não converta automaticamente `404` em erro interno da aplicação. Em muitos casos ele representa simplesmente ausência de cadastro correspondente.

### `429`

Indica que o IP excedeu o limite da API pública.

Não faça retry imediato.

Consulte também `04-limitacoes.md`.

## 17. Exemplo de requisição cURL

Exemplo criado para integração:

```bash
curl --request GET   --url "https://publica.cnpj.ws/cnpj/00000000000000"   --header "Accept: application/json"
```

## 18. Exemplo em JavaScript

```javascript
async function consultarCnpj(cnpj) {
  const normalized = cnpj.replace(/\D/g, "");

  if (normalized.length !== 14) {
    throw new Error("CNPJ deve possuir 14 dígitos");
  }

  const response = await fetch(
    `https://publica.cnpj.ws/cnpj/${normalized}`,
    { headers: { Accept: "application/json" } }
  );

  if (response.status === 429) {
    throw new Error("Rate limit da API CNPJ.ws excedido");
  }

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`Erro CNPJ.ws: HTTP ${response.status}`);
  }

  return response.json();
}
```

## 19. Exemplo em Python

```python
import re
import requests

BASE_URL = "https://publica.cnpj.ws"

def consultar_cnpj(cnpj: str) -> dict | None:
    normalized = re.sub(r"\D", "", cnpj)

    if len(normalized) != 14:
        raise ValueError("CNPJ deve possuir 14 dígitos")

    response = requests.get(
        f"{BASE_URL}/cnpj/{normalized}",
        headers={"Accept": "application/json"},
        timeout=15,
    )

    if response.status_code == 404:
        return None

    if response.status_code == 429:
        raise RuntimeError("Rate limit da API CNPJ.ws excedido")

    response.raise_for_status()
    return response.json()
```

## 20. Pacote JavaScript citado pela documentação

A documentação menciona o pacote npm:

```text
consultar-cnpj
```

Instalação apresentada:

```bash
yarn add consultar-cnpj
```

Esse pacote é uma opção de conveniência; ele não é necessário para consumir diretamente o endpoint HTTP.

## 21. Regras para agentes de IA

Ao trabalhar com este endpoint:

1. não inventar parâmetros de query não documentados;
2. usar `GET`;
3. enviar CNPJ sem máscara;
4. tratar CNPJ como string;
5. validar 14 dígitos antes da chamada;
6. respeitar 3 requisições/minuto/IP;
7. tratar `404` e `429` explicitamente;
8. aceitar `null` em campos opcionais;
9. não assumir que o retorno está atualizado em tempo real;
10. não usar esse endpoint para rotinas de alto volume sem estratégia de cache/fila ou sem avaliar a API comercial.
