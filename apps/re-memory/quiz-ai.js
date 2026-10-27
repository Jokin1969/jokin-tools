// Generate quiz questions using Claude API
// Based on memory content, creates 10 questions with 4 multiple-choice options each

const db = require('./db');

async function generateQuizQuestions(quizId, memoryDescription, memoryTopic) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error('ANTHROPIC_API_KEY no configurada');
  }

  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey });

  const prompt = `Basándote en la siguiente información sobre un tema, genera 10 preguntas de opción múltiple para un cuestionario educativo.

TEMA: ${memoryTopic}
INFORMACIÓN:
${memoryDescription}

Requisitos:
1. Crea exactamente 10 preguntas
2. Cada pregunta debe tener 4 opciones de respuesta
3. Una opción es correcta, las otras 3 son distractores creíbles
4. Las preguntas deben variar en dificultad (fácil, medio, difícil)
5. Cada pregunta tiene una explicación clara del por qué la respuesta es correcta

Responde ÚNICAMENTE en formato JSON válido (sin backticks, sin explicaciones adicionales):
{
  "questions": [
    {
      "question": "¿Pregunta aquí?",
      "options": ["opción A", "opción B", "opción C", "opción D"],
      "correct_answer": "opción correcta",
      "explanation": "Explicación clara de por qué esta es la respuesta correcta"
    }
  ]
}

Importante: El formato debe ser JSON puro, válido y parseble.`;

  try {
    const msg = await client.messages.create({
      model: 'claude-opus-5-5',
      max_tokens: 4000,
      messages: [{ role: 'user', content: prompt }],
    });

    const textBlock = (msg.content || []).find(b => b.type === 'text');
    if (!textBlock) throw new Error('Claude no devolvió texto');

    let jsonText = textBlock.text.trim();
    // Limpiar si viene con backticks
    if (jsonText.startsWith('```json')) {
      jsonText = jsonText.replace(/^```json\s*/, '').replace(/\s*```$/, '');
    } else if (jsonText.startsWith('```')) {
      jsonText = jsonText.replace(/^```\s*/, '').replace(/\s*```$/, '');
    }

    const parsed = JSON.parse(jsonText);

    if (!Array.isArray(parsed.questions) || parsed.questions.length !== 10) {
      throw new Error('La IA no generó exactamente 10 preguntas');
    }

    // Insertar preguntas en la BD
    for (let i = 0; i < parsed.questions.length; i++) {
      const q = parsed.questions[i];

      if (!q.question || !q.options || q.options.length !== 4 || !q.correct_answer) {
        throw new Error(`Pregunta ${i + 1} incompleta o mal formada`);
      }

      const questionId = db.addQuizQuestion(quizId, {
        question: q.question,
        order_num: i + 1,
        correct_answer: q.correct_answer,
        explanation: q.explanation || ''
      });

      // Insertar opciones
      for (let j = 0; j < q.options.length; j++) {
        db.addQuizOption(questionId, q.options[j], j + 1);
      }
    }

    console.log(`[quiz-ai] Generated 10 questions for quiz ${quizId}`);
    return true;
  } catch (error) {
    console.error('[quiz-ai] Error generating questions:', error.message);
    throw error;
  }
}

module.exports = { generateQuizQuestions };
