// Quiz interaction logic

let quiz = null;
let questions = [];
let answers = {}; // { questionId: selectedAnswer }
let currentQuestionIndex = 0;

async function loadQuiz() {
  try {
    const token = new URLSearchParams(window.location.search).get('token');
    if (!token) {
      showError('Token de cuestionario no válido');
      return;
    }

    const resp = await fetch(`/re-memory/api/quiz/${token}`);
    if (!resp.ok) throw new Error('Cuestionario no encontrado');

    quiz = await resp.json();
    questions = quiz.questions || [];

    if (questions.length === 0) {
      showError('El cuestionario está vacío');
      return;
    }

    // Initialize answers object
    questions.forEach(q => {
      answers[q.id] = null;
    });

    // Show quiz UI
    document.getElementById('loading-state').style.display = 'none';
    document.getElementById('quiz-header').style.display = 'block';
    document.getElementById('nav-buttons').style.display = 'flex';

    document.getElementById('quiz-topic').textContent = quiz.topic || 'Cuestionario';
    document.getElementById('quiz-subtitle').textContent = `Tema: ${quiz.description.substring(0, 80)}...`;

    renderQuestion(0);
  } catch (error) {
    showError('Error cargando cuestionario: ' + error.message);
  }
}

function renderQuestion(index) {
  if (index < 0 || index >= questions.length) return;

  currentQuestionIndex = index;
  const question = questions[index];

  // Update progress
  document.getElementById('current-question').textContent = index + 1;
  const progress = ((index + 1) / questions.length) * 100;
  document.getElementById('progress-bar').style.width = progress + '%';

  // Render question and options
  const container = document.getElementById('quiz-questions');
  container.innerHTML = `
    <div class="question-card active">
      <span class="question-number">Pregunta ${index + 1} de ${questions.length}</span>
      <div class="question-text">${escapeHtml(question.question)}</div>
      <div class="options-group">
        ${question.options.map((opt, i) => `
          <button class="option-btn ${answers[question.id] === opt.text ? 'selected' : ''}"
                  onclick="selectAnswer(${question.id}, '${escapeAttr(opt.text)}')">
            <div class="option-radio"></div>
            <span>${escapeHtml(opt.text)}</span>
          </button>
        `).join('')}
      </div>
    </div>
  `;

  // Update navigation
  document.getElementById('btn-prev').disabled = index === 0;
  document.getElementById('btn-next').disabled = answers[question.id] === null;
  document.getElementById('btn-next').textContent =
    index === questions.length - 1 ? 'Enviar respuestas' : 'Siguiente →';
}

function selectAnswer(questionId, answer) {
  answers[questionId] = answer;
  renderQuestion(currentQuestionIndex);
}

document.getElementById('btn-prev')?.addEventListener('click', () => {
  renderQuestion(currentQuestionIndex - 1);
});

document.getElementById('btn-next')?.addEventListener('click', async () => {
  if (currentQuestionIndex === questions.length - 1) {
    await submitQuiz();
  } else {
    renderQuestion(currentQuestionIndex + 1);
  }
});

async function submitQuiz() {
  const token = new URLSearchParams(window.location.search).get('token');

  try {
    // Submit all responses
    for (const question of questions) {
      const answer = answers[question.id];
      if (answer) {
        await fetch(`/re-memory/api/quiz/${token}/answer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question_id: question.id,
            answer: answer
          })
        });
      }
    }

    // Get results
    const resultResp = await fetch(`/re-memory/api/quiz/${token}/result`);
    if (!resultResp.ok) throw new Error('Error obteniendo resultados');

    const result = await resultResp.json();
    showResults(result);
  } catch (error) {
    showError('Error enviando respuestas: ' + error.message);
  }
}

function showResults(result) {
  // Hide quiz, show results
  document.getElementById('quiz-header').style.display = 'none';
  document.getElementById('quiz-questions').style.display = 'none';
  document.getElementById('nav-buttons').style.display = 'none';
  document.getElementById('results-screen').classList.add('active');

  const score = result.score;
  const scoreCircle = document.getElementById('score-circle');
  const scoreMessage = document.getElementById('score-message');
  const scoreFeedback = document.getElementById('score-feedback');

  // Set score circle color and message
  if (score >= 90) {
    scoreCircle.classList.add('excellent');
    scoreMessage.textContent = '¡Excelente!';
    scoreFeedback.textContent = 'Demuestras dominar muy bien este tema.';
  } else if (score >= 70) {
    scoreCircle.classList.add('good');
    scoreMessage.textContent = '¡Muy bien!';
    scoreFeedback.textContent = 'Tienes un buen conocimiento del tema.';
  } else if (score >= 50) {
    scoreCircle.classList.add('poor');
    scoreMessage.textContent = 'Aprobado';
    scoreFeedback.textContent = 'Podrías repasar algunos conceptos.';
  } else {
    scoreCircle.classList.add('fail');
    scoreMessage.textContent = 'Reprobado';
    scoreFeedback.textContent = 'Te recomendamos revisar la información y intentar de nuevo.';
  }

  scoreCircle.textContent = score + '%';

  // Show feedback for incorrect answers
  const feedbackContainer = document.getElementById('feedback-items');
  feedbackContainer.innerHTML = '';

  result.responses.forEach(response => {
    if (!response.is_correct) {
      const feedback = document.createElement('div');
      feedback.className = 'feedback-item incorrect';
      feedback.innerHTML = `
        <div class="feedback-question">❌ ${escapeHtml(response.question)}</div>
        <div class="feedback-answer">
          <span class="feedback-label">Tu respuesta:</span>
          ${escapeHtml(response.user_answer)}
        </div>
        <div class="feedback-answer">
          <span class="feedback-label">Respuesta correcta:</span>
          ${escapeHtml(response.correct_answer)}
        </div>
        <div class="feedback-explanation">
          <strong>Explicación:</strong> ${escapeHtml(response.explanation || 'No hay explicación disponible')}
        </div>
      `;
      feedbackContainer.appendChild(feedback);
    }
  });

  // Show correct answers summary
  const correctCount = result.responses.filter(r => r.is_correct).length;
  if (correctCount > 0) {
    const summary = document.createElement('div');
    summary.className = 'feedback-item correct';
    summary.innerHTML = `
      <div class="feedback-question">✓ ${correctCount} respuestas correctas</div>
      <div class="feedback-answer">Bien hecho en estas preguntas</div>
    `;
    feedbackContainer.insertBefore(summary, feedbackContainer.firstChild);
  }
}

function showError(message) {
  document.getElementById('loading-state').style.display = 'none';
  const errorEl = document.getElementById('error-state');
  errorEl.textContent = message;
  errorEl.style.display = 'block';
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeAttr(text) {
  return text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// Load quiz on page load
window.addEventListener('DOMContentLoaded', loadQuiz);
