// Cuestionario: carga las preguntas, recoge las respuestas y envía todo de una vez.
const $ = id => document.getElementById(id);
const token = new URLSearchParams(window.location.search).get('token');

let questions = [];
const answers = {}; // { questionId: textoElegido }
let current = 0;

async function api(path, opts) {
  const r = await fetch(`/re-memory/api/quiz/${encodeURIComponent(token)}${path}`, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Error ${r.status}`);
  return data;
}

async function loadQuiz() {
  if (!token) return showError('Falta el código del cuestionario en el enlace.');
  try {
    const data = await api('');
    if (data.status === 'completed') return showResults(data);

    questions = data.questions || [];
    if (!questions.length) return showError('Este cuestionario no tiene preguntas.');

    $('loading-state').style.display = 'none';
    $('quiz-header').style.display = 'block';
    $('nav-buttons').style.display = 'flex';
    $('quiz-topic').textContent = data.topic || 'Cuestionario';
    const desc = data.description || '';
    $('quiz-subtitle').textContent = desc.length > 90 ? desc.slice(0, 90) + '…' : desc;
    $('total-questions').textContent = questions.length;
    renderQuestion(0);
  } catch (err) {
    showError('No se pudo cargar el cuestionario: ' + err.message);
  }
}

function renderQuestion(index) {
  if (index < 0 || index >= questions.length) return;
  current = index;
  const q = questions[index];

  $('current-question').textContent = index + 1;
  $('progress-bar').style.width = ((index + 1) / questions.length) * 100 + '%';

  const card = document.createElement('div');
  card.className = 'question-card active';
  card.innerHTML = `
    <span class="question-number">Pregunta ${index + 1} de ${questions.length}</span>
    <div class="question-text"></div>
    <div class="options-group"></div>`;
  card.querySelector('.question-text').textContent = q.question;

  const group = card.querySelector('.options-group');
  q.options.forEach(opt => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'option-btn' + (answers[q.id] === opt.text ? ' selected' : '');
    btn.innerHTML = '<div class="option-radio"></div><span></span>';
    btn.querySelector('span').textContent = opt.text;
    btn.addEventListener('click', () => { answers[q.id] = opt.text; renderQuestion(current); });
    group.appendChild(btn);
  });

  $('quiz-questions').replaceChildren(card);
  $('btn-prev').disabled = index === 0;
  $('btn-next').disabled = !answers[q.id];
  $('btn-next').textContent = index === questions.length - 1 ? 'Enviar respuestas' : 'Siguiente →';
}

$('btn-prev').addEventListener('click', () => renderQuestion(current - 1));
$('btn-next').addEventListener('click', () => {
  if (current < questions.length - 1) return renderQuestion(current + 1);
  submitQuiz();
});

async function submitQuiz() {
  const btn = $('btn-next');
  btn.disabled = true;
  btn.textContent = 'Corrigiendo…';
  try {
    const result = await api('/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        answers: Object.entries(answers).map(([id, answer]) => ({ question_id: Number(id), answer })),
      }),
    });
    showResults(result);
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Enviar respuestas';
    alert('No se pudieron enviar las respuestas: ' + err.message);
  }
}

function showResults(data) {
  $('loading-state').style.display = 'none';
  $('quiz-header').style.display = 'none';
  $('quiz-questions').style.display = 'none';
  $('nav-buttons').style.display = 'none';
  $('results-screen').classList.add('active');

  const score = data.score || 0;
  const levels = [
    [90, 'excellent', '¡Excelente!', 'Dominas este tema.'],
    [70, 'good', '¡Muy bien!', 'Tienes un buen conocimiento del tema.'],
    [50, 'poor', 'Aprobado', 'Te vendrá bien repasar algunos puntos.'],
    [0, 'fail', 'Suspenso', 'Repasa la ficha: abajo tienes por qué cada respuesta era la buena.'],
  ];
  const [, cls, msg, fb] = levels.find(([min]) => score >= min);
  $('score-circle').className = 'score-circle ' + cls;
  $('score-circle').textContent = score + '%';
  $('score-message').textContent = (data.topic ? data.topic + ' · ' : '') + msg;
  $('score-feedback').textContent = fb;

  const results = data.results || [];
  const box = $('feedback-items');
  box.replaceChildren();

  const ok = results.filter(r => r.is_correct).length;
  box.appendChild(feedbackItem('correct', `✓ ${ok} de ${results.length} correctas`));

  results.filter(r => !r.is_correct).forEach(r => {
    const item = feedbackItem('incorrect', '✗ ' + r.question);
    addLine(item, 'Tu respuesta:', r.user_answer || 'sin contestar');
    addLine(item, 'Respuesta correcta:', r.correct_answer);
    const exp = document.createElement('div');
    exp.className = 'feedback-explanation';
    exp.innerHTML = '<strong>Por qué:</strong> ';
    exp.append(r.explanation || 'Sin explicación.');
    item.appendChild(exp);
    box.appendChild(item);
  });
}

function feedbackItem(kind, title) {
  const el = document.createElement('div');
  el.className = 'feedback-item ' + kind;
  const t = document.createElement('div');
  t.className = 'feedback-question';
  t.textContent = title;
  el.appendChild(t);
  return el;
}

function addLine(item, label, value) {
  const line = document.createElement('div');
  line.className = 'feedback-answer';
  const l = document.createElement('span');
  l.className = 'feedback-label';
  l.textContent = label + ' ';
  line.append(l, value);
  item.appendChild(line);
}

function showError(message) {
  $('loading-state').style.display = 'none';
  $('error-state').textContent = message;
  $('error-state').style.display = 'block';
}

loadQuiz();
