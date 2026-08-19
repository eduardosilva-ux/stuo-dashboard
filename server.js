// Servidor-ponte simples: guarda a chave da Anthropic no servidor
// e repassa as chamadas do simulador HTML. Assim quem abre o HTML
// nunca precisa ter (nem ver) uma chave de API.

const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json({ limit: "1mb" }));

const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const APP_SECRET = process.env.APP_SECRET; // senha simples de acesso ao proxy (opcional, mas recomendado)

if (!ANTHROPIC_API_KEY) {
  console.error("ERRO: defina a variável de ambiente ANTHROPIC_API_KEY antes de iniciar o servidor.");
  process.exit(1);
}

app.get("/", (req, res) => {
  res.send("Proxy do Simulador Stuo está no ar.");
});

app.post("/chat", async (req, res) => {
  try {
    // Proteção simples: se APP_SECRET estiver configurado, exige o header correspondente.
    // Isso evita que, se a URL do proxy vazar, qualquer pessoa consiga usar sua chave.
    if (APP_SECRET) {
      const provided = req.headers["x-app-secret"];
      if (provided !== APP_SECRET) {
        return res.status(401).json({ error: { message: "Não autorizado." } });
      }
    }

    const { system, messages } = req.body;
    if (!Array.isArray(messages)) {
      return res.status(400).json({ error: { message: "Campo 'messages' é obrigatório e deve ser um array." } });
    }

    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 1000,
        system: system || "",
        messages
      })
    });

    const data = await response.json();

    if (!response.ok) {
      return res.status(response.status).json(data);
    }

    res.json(data);
  } catch (err) {
    console.error("Erro no proxy:", err);
    res.status(500).json({ error: { message: "Erro interno no proxy." } });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Proxy do Simulador Stuo rodando na porta ${PORT}`);
});
