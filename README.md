# automations

Orquestrador de jobs configurável, dirigido por arquivo. Jobs em `jobs.yaml`; segredos e globais no `.env`. Sem código por job.

## Quick start
```bash
pip install -e .
copy .env.example .env
copy jobs.example.yaml jobs.yaml
automate validate --config jobs.yaml
```