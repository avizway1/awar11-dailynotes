// Frontend logic for the Aviz Academy To-Do list app.

const API_URL = '/api/tasks';

// Page elements
const form = document.getElementById('task-form');
const formCard = document.getElementById('form-card');
const formHeading = document.getElementById('form-heading');
const formSubheading = document.getElementById('form-subheading');
const taskIdInput = document.getElementById('task-id');
const titleInput = document.getElementById('title');
const descriptionInput = document.getElementById('description');
const dueDateInput = document.getElementById('dueDate');
const submitBtn = document.getElementById('submit-btn');
const cancelBtn = document.getElementById('cancel-btn');
const formError = document.getElementById('form-error');
const taskList = document.getElementById('task-list');
const emptyMessage = document.getElementById('empty-message');
const overdueChip = document.getElementById('overdue-chip');
const filterButtons = document.querySelectorAll('.filter');

let currentFilter = 'all';
let allTasks = [];
let flashId = null; // task to highlight after adding or saving

/* ---------------- Load and show tasks ---------------- */

async function loadTasks() {
  // Fetch every task once, then filter in the browser so the
  // counters on the filter buttons always show the full picture.
  const response = await fetch(API_URL);
  allTasks = await response.json();

  // Pending tasks first, then completed ones, each by due date.
  allTasks.sort((a, b) => {
    if (a.status !== b.status) return a.status === 'pending' ? -1 : 1;
    return a.dueDate.localeCompare(b.dueDate);
  });

  updateCounts();
  render(allTasks.filter(matchesFilter));
}

function matchesFilter(task) {
  return currentFilter === 'all' || task.status === currentFilter;
}

function updateCounts() {
  const pending = allTasks.filter((t) => t.status === 'pending').length;
  const completed = allTasks.length - pending;
  const overdue = allTasks.filter((t) => t.isOverdue).length;

  document.getElementById('count-all').textContent = allTasks.length;
  document.getElementById('count-pending').textContent = pending;
  document.getElementById('count-completed').textContent = completed;

  overdueChip.classList.toggle('hidden', overdue === 0);
  overdueChip.textContent = overdue + (overdue === 1 ? ' overdue task' : ' overdue tasks');
}

function render(tasks) {
  taskList.innerHTML = '';
  emptyMessage.classList.toggle('hidden', tasks.length > 0);

  tasks.forEach((task, index) => taskList.appendChild(buildTaskItem(task, index)));

  flashId = null;
}

function buildTaskItem(task, index) {
  const item = document.createElement('li');
  item.className = 'task';
  item.style.setProperty('--i', index); // staggers the entry animation

  if (task.status === 'completed') {
    item.classList.add('completed');
  } else if (task.isOverdue) {
    item.classList.add('overdue');
  } else if (task.isDueSoon) {
    item.classList.add('due-soon');
  }

  if (String(task.id) === String(flashId)) item.classList.add('flash');

  // Checkbox -> marks completed / back to pending
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.checked = task.status === 'completed';
  checkbox.title = task.status === 'completed' ? 'Move back to pending' : 'Mark as completed';
  checkbox.addEventListener('change', () => toggleTask(task.id));

  // Text part
  const body = document.createElement('div');
  body.className = 'task-body';

  const title = document.createElement('div');
  title.className = 'task-title';
  title.textContent = task.title;
  body.appendChild(title);

  if (task.description) {
    const desc = document.createElement('div');
    desc.className = 'task-desc';
    desc.textContent = task.description;
    body.appendChild(desc);
  }

  const meta = document.createElement('div');
  meta.className = 'task-meta';

  const due = document.createElement('span');
  due.textContent = 'Due ' + formatDate(task.dueDate);
  meta.appendChild(due);

  if (task.status === 'completed') {
    meta.appendChild(makeBadge('completed', 'badge-done'));
  } else {
    meta.appendChild(makeBadge('pending', 'badge-status'));

    if (task.isOverdue) {
      const late = Math.abs(task.daysLeft);
      meta.appendChild(makeBadge('Overdue by ' + late + (late === 1 ? ' day' : ' days'), 'badge-overdue'));
    } else if (task.isDueSoon) {
      const text = task.daysLeft === 0
        ? 'Due today'
        : 'Due in ' + task.daysLeft + (task.daysLeft === 1 ? ' day' : ' days');
      meta.appendChild(makeBadge(text, 'badge-soon'));
    }
  }

  body.appendChild(meta);

  // Buttons
  const actions = document.createElement('div');
  actions.className = 'task-actions';

  const editBtn = document.createElement('button');
  editBtn.className = 'small-btn';
  editBtn.textContent = 'Edit';
  editBtn.addEventListener('click', () => startEdit(task));

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'small-btn delete';
  deleteBtn.textContent = 'Delete';
  deleteBtn.addEventListener('click', () => deleteTask(task.id));

  actions.appendChild(editBtn);
  actions.appendChild(deleteBtn);

  item.appendChild(checkbox);
  item.appendChild(body);
  item.appendChild(actions);

  trackPointer(item); // spotlight follows the cursor

  return item;
}

function makeBadge(text, className) {
  const badge = document.createElement('span');
  badge.className = 'badge ' + className;
  badge.textContent = text;
  return badge;
}

// "2026-09-05" -> "05 Sep 2026"
function formatDate(value) {
  const date = new Date(value + 'T00:00:00');
  if (isNaN(date.getTime())) return value;

  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

/* ---------------- Create / update ---------------- */

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  hideError();

  const data = {
    title: titleInput.value.trim(),
    description: descriptionInput.value.trim(),
    dueDate: dueDateInput.value
  };

  if (!data.title) return showError('Please enter a task title.');
  if (!data.dueDate) return showError('Please pick a due date.');

  const editingId = taskIdInput.value;
  const response = await fetch(editingId ? API_URL + '/' + editingId : API_URL, {
    method: editingId ? 'PUT' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });

  const result = await response.json();
  if (!response.ok) return showError(result.error || 'Something went wrong.');

  flashId = result.id;
  resetForm();
  loadTasks();
});

function startEdit(task) {
  taskIdInput.value = task.id;
  titleInput.value = task.title;
  descriptionInput.value = task.description || '';
  dueDateInput.value = task.dueDate;

  formCard.classList.add('editing');
  formHeading.textContent = 'Edit task';
  formSubheading.textContent = 'Update the details and save your changes';
  submitBtn.querySelector('.btn-label').textContent = 'Save changes';
  cancelBtn.classList.remove('hidden');

  hideError();
  formCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
  titleInput.focus();
}

cancelBtn.addEventListener('click', resetForm);

function resetForm() {
  form.reset();
  taskIdInput.value = '';

  formCard.classList.remove('editing');
  formHeading.textContent = 'Add a new task';
  formSubheading.textContent = 'Fill in the details and press Add task';
  submitBtn.querySelector('.btn-label').textContent = 'Add task';
  cancelBtn.classList.add('hidden');

  hideError();
}

/* ---------------- Toggle / delete ---------------- */

async function toggleTask(id) {
  await fetch(API_URL + '/' + id + '/toggle', { method: 'PATCH' });
  loadTasks();
}

async function deleteTask(id) {
  if (!confirm('Delete this task?')) return;

  await fetch(API_URL + '/' + id, { method: 'DELETE' });

  // If we were editing that task, clear the form.
  if (taskIdInput.value === String(id)) resetForm();

  loadTasks();
}

/* ---------------- Filters ---------------- */

filterButtons.forEach((button) => {
  button.addEventListener('click', () => {
    filterButtons.forEach((b) => b.classList.remove('active'));
    button.classList.add('active');
    currentFilter = button.dataset.filter;
    render(allTasks.filter(matchesFilter));
  });
});

/* ---------------- Cursor effects ---------------- */

// Tells the CSS where the pointer is inside a card, so the
// spotlight in ::before can follow it.
function trackPointer(element) {
  element.addEventListener('mousemove', (event) => {
    const box = element.getBoundingClientRect();
    element.style.setProperty('--mx', (event.clientX - box.left) + 'px');
    element.style.setProperty('--my', (event.clientY - box.top) + 'px');
  });
}

trackPointer(formCard);

// Soft halo that eases towards the pointer.
const glow = document.getElementById('cursor-glow');
let pointerX = window.innerWidth / 2;
let pointerY = window.innerHeight / 2;
let glowX = pointerX;
let glowY = pointerY;

document.addEventListener('mousemove', (event) => {
  pointerX = event.clientX;
  pointerY = event.clientY;
  glow.style.opacity = '1';
});

document.addEventListener('mouseleave', () => { glow.style.opacity = '0'; });

(function animateGlow() {
  glowX += (pointerX - glowX) * 0.08;
  glowY += (pointerY - glowY) * 0.08;
  glow.style.transform = 'translate(' + glowX + 'px, ' + glowY + 'px)';
  requestAnimationFrame(animateGlow);
})();

/* ---------------- Small helpers ---------------- */

function showError(message) {
  formError.textContent = message;
  formError.classList.remove('hidden');
}

function hideError() {
  formError.classList.add('hidden');
}

// Today's date in the header
document.getElementById('today-label').textContent = new Date().toLocaleDateString('en-GB', {
  weekday: 'short', day: '2-digit', month: 'short', year: 'numeric'
});

// First load
loadTasks();
