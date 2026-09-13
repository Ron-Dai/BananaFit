(() => {
  'use strict';

  const elements = {
    account: document.querySelector('[data-account-link]'),
    step: document.querySelector('[data-step]'),
    progressBar: document.querySelector('[data-progress-bar]'),
    progressLabel: document.querySelector('[data-progress-label]'),
    stage: document.querySelector('[data-stage-label]'),
    title: document.querySelector('[data-card-title]'),
    subtitle: document.querySelector('[data-card-subtitle]'),
    status: document.querySelector('[data-status-message]'),
    questions: document.querySelector('[data-questions]'),
    consent: document.querySelector('[data-provider-consent]'),
    consentInput: document.querySelector('[data-provider-consent-input]'),
    back: document.querySelector('[data-back]'),
    save: document.querySelector('[data-save]'),
    continue: document.querySelector('[data-continue]'),
  };

  const DRAFT_KEY = 'forgefit-intake-draft-v1';
  const previewQuestions = [
    {
      field_path: 'immediate_screen.current_chest_discomfort',
      text: 'Do you currently have new, significant, or unexplained chest pressure, tightness, or pain?',
      answer_type: 'bool',
      reason: 'Current symptoms take priority over all training decisions.',
      options: {},
    },
    {
      field_path: 'immediate_screen.severe_rest_dyspnea',
      text: 'Are you currently having marked difficulty breathing even at rest?',
      answer_type: 'bool',
      reason: 'Current symptoms take priority over all training decisions.',
      options: {},
    },
    {
      field_path: 'immediate_screen.current_fainting_or_confusion',
      text: 'Are you currently fainting, close to fainting, or newly confused?',
      answer_type: 'bool',
      reason: 'Current symptoms take priority over all training decisions.',
      options: {},
    },
  ];

  let user = null;
  let questionnaire = null;
  let csrfToken = null;
  let mode = 'questions';

  const create = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  const showStatus = (message, type = 'error') => {
    elements.status.textContent = message;
    elements.status.className = `status-message visible ${type}`;
  };

  const clearStatus = () => {
    elements.status.textContent = '';
    elements.status.className = 'status-message';
  };

  const api = async (url, options = {}) => {
    const response = await fetch(url, { credentials: 'same-origin', ...options });
    let body = {};
    try { body = await response.json(); } catch (_error) { /* use safe fallback */ }
    if (!response.ok) {
      const error = new Error(body?.error?.message || 'The request could not be completed.');
      error.status = response.status;
      error.code = body?.error?.code;
      throw error;
    }
    return body;
  };

  const csrf = async () => {
    const body = await api('/api/auth/csrf');
    csrfToken = body.csrf_token;
    return csrfToken;
  };

  const mutation = async (url, body) => {
    if (!csrfToken) await csrf();
    try {
      return await api(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
        body: JSON.stringify(body),
      });
    } catch (error) {
      if (error.code === 'csrf_failed') {
        await csrf();
        return api(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
          body: JSON.stringify(body),
        });
      }
      throw error;
    }
  };

  const radioChoice = (name, label, status, value) => {
    const wrapper = create('label', 'choice');
    const input = create('input');
    input.type = 'radio';
    input.name = name;
    input.dataset.status = status;
    if (value !== undefined) input.dataset.value = JSON.stringify(value);
    wrapper.append(input, create('span', '', label));
    return wrapper;
  };

  const renderBoolean = (question, holder) => {
    const choices = create('div', 'choices');
    choices.append(
      radioChoice(question.field_path, 'No', 'answered', false),
      radioChoice(question.field_path, 'Yes', 'answered', true),
      radioChoice(question.field_path, 'Prefer not to answer', 'declined')
    );
    holder.append(choices);
  };

  const renderEnum = (question, holder) => {
    const choices = create('div', 'choices');
    Object.entries(question.options || {}).forEach(([value, label]) => {
      choices.append(radioChoice(question.field_path, label, 'answered', value));
    });
    choices.append(radioChoice(question.field_path, 'Prefer not to answer', 'declined'));
    holder.append(choices);
  };

  const renderMulti = (question, holder) => {
    const choices = create('div', 'choices');
    Object.entries(question.options || {}).forEach(([value, label]) => {
      const wrapper = create('label', 'choice');
      const input = create('input');
      input.type = 'checkbox';
      input.name = question.field_path;
      input.value = value;
      wrapper.append(input, create('span', '', label));
      choices.append(wrapper);
    });
    choices.append(radioChoice(`${question.field_path}-missing`, 'Prefer not to answer', 'declined'));
    holder.append(choices);
  };

  const renderScalar = (question, holder) => {
    const area = create('div', 'scalar-area');
    const row = create('div', 'scalar-row');
    const input = question.answer_type === 'text' ? create('textarea') : create('input');
    input.dataset.scalar = question.field_path;
    if (question.answer_type === 'integer' || question.answer_type === 'number' ||
        question.answer_type === 'measurement') {
      input.type = 'number';
      input.step = question.answer_type === 'integer' ? '1' : 'any';
    } else if (question.answer_type === 'date') {
      input.type = 'date';
    } else if (question.answer_type === 'datetime') {
      input.type = 'datetime-local';
    } else {
      input.placeholder = 'Type your answer';
    }
    row.append(input);
    if (question.unit) row.append(create('span', 'unit', question.unit));
    const missing = create('div', 'choices');
    missing.append(
      radioChoice(`${question.field_path}-missing`, 'I’m not sure', 'unknown'),
      radioChoice(`${question.field_path}-missing`, 'Prefer not to answer', 'declined')
    );
    area.append(row, missing);
    holder.append(area);
  };

  const recordField = (definition) => {
    const wrapper = create('div', `record-field ${definition.type === 'text' ? 'wide' : ''}`);
    wrapper.dataset.recordField = definition.name;
    wrapper.dataset.type = definition.type;
    wrapper.dataset.unit = definition.unit || '';
    wrapper.append(create('label', '', definition.label));
    const kind = definition.type.split(':')[0];
    let input;
    if (kind === 'enum') {
      input = create('select');
      input.append(new Option('Select an option', ''));
      Object.entries(definition.options || {}).forEach(([value, label]) => {
        input.append(new Option(label, value));
      });
    } else if (kind === 'multi') {
      input = create('select');
      input.multiple = true;
      Object.entries(definition.options || {}).forEach(([value, label]) => {
        input.append(new Option(label, value));
      });
    } else if (kind === 'bool') {
      input = create('select');
      input.append(new Option('Select an option', ''), new Option('No', 'false'), new Option('Yes', 'true'));
    } else if (kind === 'text') {
      input = create('textarea');
      input.placeholder = 'Enter details';
    } else {
      input = create('input');
      input.type = ['integer', 'number', 'measurement'].includes(kind) ? 'number' :
        kind === 'date' ? 'date' : kind === 'datetime' ? 'datetime-local' : 'text';
      if (input.type === 'number') input.step = kind === 'integer' ? '1' : 'any';
    }
    wrapper.append(input);
    return wrapper;
  };

  const addRecordEntry = (list, schema) => {
    const entry = create('section', 'record-entry');
    const header = create('header');
    header.append(create('strong', '', `${schema.record_name.replaceAll('_', ' ')} details`));
    const remove = create('button', 'text-button', 'Remove');
    remove.type = 'button';
    remove.addEventListener('click', () => entry.remove());
    header.append(remove);
    const grid = create('div', 'record-grid');
    schema.fields.forEach((field) => grid.append(recordField(field)));
    entry.append(header, grid);
    list.append(entry);
  };

  const renderRecord = (question, schema, holder) => {
    const area = create('div', 'record-editor');
    const modeChoices = create('div', 'choices');
    modeChoices.append(
      radioChoice(`${question.field_path}-record-mode`, 'Nothing to report', 'answered', []),
      radioChoice(`${question.field_path}-record-mode`, 'Add details', 'details'),
      radioChoice(`${question.field_path}-record-mode`, 'Prefer not to answer', 'declined')
    );
    const list = create('div', 'record-list');
    list.dataset.recordList = question.field_path;
    const add = create('button', 'text-button', '+ Add another');
    add.type = 'button';
    add.hidden = true;
    add.addEventListener('click', () => addRecordEntry(list, schema));
    modeChoices.addEventListener('change', (event) => {
      const details = event.target.dataset.status === 'details';
      add.hidden = !details;
      if (details && !list.children.length) addRecordEntry(list, schema);
      if (!details) list.textContent = '';
    });
    area.append(modeChoices, list, add);
    holder.append(area);
  };

  const renderQuestions = (questions, schemas = {}) => {
    mode = 'questions';
    elements.questions.textContent = '';
    elements.consent.hidden = true;
    elements.continue.textContent = 'Continue';
    questions.forEach((question, index) => {
      const card = create('article', 'question');
      card.dataset.path = question.field_path;
      card.dataset.type = question.answer_type;
      card.dataset.unit = question.unit || '';
      card.append(
        create('h3', '', `${index + 1}. ${question.text}`),
        create('p', 'reason', question.reason)
      );
      if (question.answer_type === 'bool') renderBoolean(question, card);
      else if (question.answer_type.startsWith('enum:')) renderEnum(question, card);
      else if (question.answer_type.startsWith('multi:')) renderMulti(question, card);
      else if (question.answer_type.startsWith('record:')) {
        renderRecord(question, schemas[question.field_path] || { record_name: 'record', fields: [] }, card);
      } else renderScalar(question, card);
      elements.questions.append(card);
    });
  };

  const renderReview = (readiness) => {
    mode = readiness.status === 'emergency' ? 'emergency' : 'review';
    elements.questions.textContent = '';
    elements.title.textContent = readiness.status === 'emergency' ?
      'Pause and review this safety guidance' : 'Your intake is ready for review';
    elements.subtitle.textContent = readiness.planning_scope ||
      'Review the information before generating your two-week plan.';
    const panel = create('section', 'review-panel');
    panel.append(create('h3', '', `Readiness: ${readiness.status.replaceAll('_', ' ')}`));
    panel.append(create('p', '', readiness.status === 'emergency' ?
      'A plan cannot be generated while an urgent safety flag is present.' :
      'Your answers have been saved. Plan generation will use the validated fitness-intake rules.'));
    const flags = create('div', 'flags');
    (readiness.flags || []).forEach((flag) => {
      const item = create('div', 'flag');
      item.append(create('strong', '', flag.description), create('span', '', flag.next_step));
      flags.append(item);
    });
    if (flags.children.length) panel.append(flags);
    elements.questions.append(panel);
    elements.consent.hidden = mode !== 'review';
    elements.continue.hidden = mode === 'emergency';
    elements.continue.textContent = 'Generate my plan';
  };

  const updateHeader = (state) => {
    const stage = state?.stage || { number: 2, total: 6, label: 'Safety' };
    const progress = state?.progress_percent ?? 32;
    elements.step.textContent = `Step ${stage.number} of ${stage.total}`;
    elements.stage.textContent = stage.label;
    elements.progressBar.style.width = `${progress}%`;
    elements.progressLabel.textContent = `${progress}% complete`;
    if (stage.number < 6) {
      elements.title.textContent = stage.label === 'Safety' ?
        'Let’s check that training is appropriate today' : `Tell us about ${stage.label.toLowerCase()}`;
      elements.subtitle.textContent = 'Choose the answer that best describes you. You can skip any question.';
    }
  };

  const renderState = (state) => {
    questionnaire = state;
    updateHeader(state);
    if (!state.questions.length || state.readiness.status === 'emergency') {
      renderReview(state.readiness);
    } else {
      renderQuestions(state.questions, state.question_schemas);
    }
  };

  const answered = (status, value, unit = null) => {
    const answer = { status, source_type: 'self_report' };
    if (status === 'answered') answer.value = value;
    if (unit) answer.unit = unit;
    return answer;
  };

  const recordValue = (entry) => {
    const result = {};
    entry.querySelectorAll('[data-record-field]').forEach((field) => {
      const input = field.querySelector('input, select, textarea');
      const kind = field.dataset.type.split(':')[0];
      let value;
      if (kind === 'multi') value = [...input.selectedOptions].map((option) => option.value);
      else if (kind === 'bool') value = input.value === '' ? null : input.value === 'true';
      else if (['integer', 'number', 'measurement'].includes(kind)) {
        value = input.value === '' ? null : Number(input.value);
        if (kind === 'integer' && value !== null) value = Math.trunc(value);
      } else value = input.value.trim();
      if (value === null || value === '' || (Array.isArray(value) && !value.length)) return;
      const child = { status: 'answered', value, source_type: 'self_report' };
      if (field.dataset.unit) child.unit = field.dataset.unit;
      result[field.dataset.recordField] = child;
    });
    return result;
  };

  const collectAnswers = () => {
    const answers = {};
    for (const card of elements.questions.querySelectorAll('.question')) {
      const path = card.dataset.path;
      const type = card.dataset.type;
      if (type === 'bool' || type.startsWith('enum:')) {
        const selected = card.querySelector('input[type="radio"]:checked');
        if (!selected) throw new Error('Please answer or skip every displayed question.');
        answers[path] = answered(
          selected.dataset.status,
          selected.dataset.value === undefined ? null : JSON.parse(selected.dataset.value)
        );
      } else if (type.startsWith('multi:')) {
        const missing = card.querySelector('input[type="radio"]:checked');
        const values = [...card.querySelectorAll('input[type="checkbox"]:checked')]
          .map((input) => input.value);
        if (missing) answers[path] = answered(missing.dataset.status, null);
        else if (values.length) answers[path] = answered('answered', values);
        else throw new Error('Please select at least one option or skip the question.');
      } else if (type.startsWith('record:')) {
        const selected = card.querySelector('input[type="radio"]:checked');
        if (!selected) throw new Error('Please choose whether you have details to report.');
        if (selected.dataset.status === 'details') {
          const records = [...card.querySelectorAll('.record-entry')]
            .map(recordValue).filter((record) => Object.keys(record).length);
          if (!records.length) throw new Error('Add at least one detail or choose Nothing to report.');
          answers[path] = answered('answered', records);
        } else {
          answers[path] = answered(
            selected.dataset.status,
            selected.dataset.value === undefined ? null : JSON.parse(selected.dataset.value)
          );
        }
      } else {
        const missing = card.querySelector('input[type="radio"]:checked');
        const input = card.querySelector('[data-scalar]');
        if (missing) answers[path] = answered(missing.dataset.status, null);
        else if (input.value.trim()) {
          const kind = type.split(':')[0];
          let value = input.value.trim();
          if (['integer', 'number', 'measurement'].includes(kind)) value = Number(value);
          if (kind === 'integer') value = Math.trunc(value);
          answers[path] = answered('answered', value, card.dataset.unit || null);
        } else throw new Error('Please enter an answer or choose a skip option.');
      }
    }
    return answers;
  };

  const ensureSession = async () => {
    const current = await api('/api/intake/current');
    if (current.status === 'available') return current.session;
    const created = await mutation('/api/intake/sessions', {});
    return api(`/api/intake/sessions/${encodeURIComponent(created.session_id)}/questionnaire`);
  };

  const submitAnswers = async (answers) => {
    const next = await mutation(
      `/api/intake/sessions/${encodeURIComponent(questionnaire.session_id)}/answers`,
      {
        answers,
        expected_version: questionnaire.version,
        request_id: `web-${crypto.randomUUID()}`,
      }
    );
    renderState(next);
    showStatus('Your answers were saved.', 'success');
  };

  const continueFlow = async () => {
    clearStatus();
    elements.continue.disabled = true;
    try {
      if (mode === 'review') {
        if (!elements.consentInput.checked) {
          throw new Error('Please confirm AI processing before generating your plan.');
        }
        const consent = await mutation(
          `/api/intake/sessions/${encodeURIComponent(questionnaire.session_id)}/consent`,
          {
            consent: {
              external_ai: true,
              sensitive_sections: [],
              attachments: false,
              purpose: 'Fitness intake and fourteen-day planning',
            },
            expected_version: questionnaire.version,
          }
        );
        elements.continue.textContent = 'Generating…';
        const generated = await mutation(
          `/api/intake/sessions/${encodeURIComponent(questionnaire.session_id)}/generate-plan`,
          {
            start_date: new Date().toISOString().slice(0, 10),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            expected_version: consent.version,
          }
        );
        if (generated.current_plan.status === 'available' && generated.redirect_url) {
          window.location.assign(generated.redirect_url);
          return;
        }
        throw new Error('More information is needed before a plan can be generated.');
      }

      const answers = collectAnswers();
      if (!user) {
        sessionStorage.setItem(DRAFT_KEY, JSON.stringify(answers));
        window.location.assign('/login');
        return;
      }
      await submitAnswers(answers);
    } catch (error) {
      if (error.status === 401) {
        window.location.assign('/login');
      } else if (error.code === 'version_conflict') {
        questionnaire = await api(
          `/api/intake/sessions/${encodeURIComponent(questionnaire.session_id)}/questionnaire`
        );
        renderState(questionnaire);
        showStatus('Your intake changed in another window. The latest questions are shown.');
      } else {
        showStatus(error.message);
      }
    } finally {
      elements.continue.disabled = false;
      if (mode === 'review') elements.continue.textContent = 'Generate my plan';
    }
  };

  const initialize = async () => {
    renderQuestions(previewQuestions);
    try {
      const me = await api('/api/auth/me');
      user = me.user;
      elements.account.textContent = user.email;
      elements.account.href = '#';
      questionnaire = await ensureSession();
      renderState(questionnaire);
      const draft = sessionStorage.getItem(DRAFT_KEY);
      if (draft && questionnaire.questions.length) {
        sessionStorage.removeItem(DRAFT_KEY);
        const parsed = JSON.parse(draft);
        const allowed = new Set(questionnaire.questions.map((question) => question.field_path));
        const matching = Object.fromEntries(
          Object.entries(parsed).filter(([path]) => allowed.has(path))
        );
        if (Object.keys(matching).length) await submitAnswers(matching);
      }
    } catch (error) {
      if (error.status !== 401) showStatus(error.message);
    }
  };

  elements.continue.addEventListener('click', continueFlow);
  elements.back.addEventListener('click', () => window.history.back());
  elements.save.addEventListener('click', async () => {
    if (!user) {
      try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify(collectAnswers())); } catch (_error) {}
      window.location.assign('/login');
      return;
    }
    elements.save.disabled = true;
    clearStatus();
    try {
      if (mode === 'questions') await submitAnswers(collectAnswers());
      else showStatus('Your completed answers are saved.', 'success');
    } catch (error) {
      if (error.status === 401) window.location.assign('/login');
      else showStatus(error.message);
    } finally {
      elements.save.disabled = false;
    }
  });

  initialize();
})();
