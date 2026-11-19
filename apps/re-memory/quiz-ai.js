// Generate quiz questions using Claude API
// Based on memory content, creates 10 questions with 4 multiple-choice options each

const db = require('./db');

async function generateQuizQuestions(quizId, memoryDescription, memoryTopic, difficulty = 'mixed', numQuestions = 10) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error('ANTHROPIC_API_KEY no configurada');
  }

  const Anthropic = require('@anthropic-ai/sdk');
  const client = new Anthropic({ apiKey });

  // Define difficulty levels
  const difficultyGuide = {
    easy: `Las preguntas deben ser fáciles, enfocadas en hechos básicos y conceptos fundamentales.
           Diseñadas para que la mayoría de personas con conocimiento general puedan responder correctamente.`,
    medium: `Las preguntas deben tener dificultad media, requiriendo comprensión moderada y aplicación de conceptos.
             Incluye algunas inferencias pero nada demasiado complejo.`,
    hard: `Las preguntas deben ser difíciles, requiriendo análisis profundo, síntesis y aplicación avanzada.
           Enfócate en detalles, excepciones y relaciones complejas entre conceptos.`,
    mixed: `Distribuye las preguntas en diferentes niveles de dificultad:
            - 3 preguntas fáciles (conceptos básicos)
            - 4 preguntas de dificultad media (comprensión y aplicación)
            - 3 preguntas difíciles (análisis y síntesis)`
  };

  const difficultyDesc = difficultyGuide[difficulty] || difficultyGuide.mixed;

  const prompt = `Basándote en la siguiente información sobre un tema, genera ${numQuestions} preguntas de opción múltiple para un cuestionario educativo.

TEMA: ${memoryTopic}
INFORMACIÓN:
${memoryDescription}

NIVEL DE DIFICULTAD:
${difficultyDesc}

Requisitos:
1. Crea exactamente ${numQuestions} preguntas
2. Cada pregunta debe tener 4 opciones de respuesta
3. Una opción es correcta, las otras 3 son distractores creíbles y realistas
4. Cada pregunta tiene una explicación clara del por qué la respuesta es correcta
5. Las explicaciones deben ayudar a aprender, no solo decir que es correcto

Responde ÚNICAMENTE en formato JSON válido (sin backticks, sin explicaciones adicionales):
{
  "questions": [
    {
      "question": "¿Pregunta aquí?",
      "options": ["opción A", "opción B", "opción C", "opción D"],
      "correct_answer": "opción correcta",
      "explanation": "Explicación clara de por qué esta es la respuesta correcta y qué aprendemos"
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

    if (!Array.isArray(parsed.questions) || parsed.questions.length !== numQuestions) {
      throw new Error(`La IA no generó exactamente ${numQuestions} preguntas (generó ${parsed.questions.length})`);
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

    console.log(`[quiz-ai] Generated ${numQuestions} questions for quiz ${quizId} (difficulty: ${difficulty})`);
    return true;
  } catch (error) {
    console.error('[quiz-ai] Error generating questions:', error.message);
    throw error;
  }
}

module.exports = { generateQuizQuestions };
