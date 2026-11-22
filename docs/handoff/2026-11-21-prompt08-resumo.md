# Handoff — acesso remoto (Prompt 07)

## Como apontar o túnel

1. `npm run build` na raiz (gera `dist/`).
2. Iniciar o backend com `OCILIMIT_REMOTE_ENABLED=1`, `OCILIMIT_REMOTE_PASSWORD`,
   `OCILIMIT_PUBLIC_ORIGIN=https://...`, `OCILIMIT_ALLOWED_ORIGINS=https://...`.
3. Configurar o túnel já instalado para encaminhar **somente** a origem pública para `127.0.0.1:8000`.
   Não expor OpenCode interno, SQLite, 5173 ou portas de modelo.
4. Testar localmente com `http://localhost:5173` (modo local inalterado) e, com autorização, abrir a URL
   pública no celular e entrar com a senha.

## Ações disponíveis no navegador remoto

- Leitura: projetos/espaços, chat, plano, fila/tentativas, logs por trecho, status e diff Git, histórico, revisão.
- Escrita (confirmação explícita): enviar mensagem, revisar/aprovar plano, gerar lote, iniciar/pausar/retomar/cancelar,
  retry, commit, push e PR em rascunho.
- Locais mesmo com remoto ativo: configurar executável/credenciais, cadastrar caminhos do Windows,
  habilitar/desabilitar remoto e administrar sessões.

## Limitações que dependem da configuração real

- O túnel em si e a validação de identidade do provedor não foram configurados/testados aqui.
- Cabeçalho `Cf-Access-Authenticated-User-Email` é usado apenas como rótulo; não é prova de identidade.
- Testes de rede externa, HTTPS real e celular dependem de autorização do ambiente do usuário.
- `gh` e credencial do OpenCode seguem sem configuração real neste PC.
