import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import OpenAI from "openai";

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// ----------- PERSONALITY -----------
const personality = `
You are Girahni, a friendly, polite Indian home AI assistant.
You speak in Roman Hindi + simple English.
You respond short, natural, and human-like.
You control lights, fan, AC, music, and home automation tasks.
`;

// ----------- TEXT AI -----------
app.post("/ask", async (req, res) => {
  try {
    const userText = req.body.message;

    const response = await client.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        { role: "system", content: personality },
        { role: "user", content: userText }
      ]
    });

    const reply = response.choices[0].message.content;

    res.json({ reply });
  } catch (error) {
    res.json({ error: error.message });
  }
});

// ----------- VOICE (TTS) -----------
app.post("/voice", async (req, res) => {
  try {
    const text = req.body.text;

    const speech = await client.audio.speech.create({
      model: "gpt-4o-mini-tts",
      voice: "verse",
      input: text
    });

    const buffer = Buffer.from(await speech.arrayBuffer());

    res.set({ "Content-Type": "audio/mpeg" });
    res.send(buffer);

  } catch (error) {
    res.json({ error: error.message });
  }
});

// ----------- SERVER START -----------
app.listen(3000, () => {
  console.log("Girahni AI Server running on port 3000");
});
