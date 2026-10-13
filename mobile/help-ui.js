'use strict';
// Local, accessible help. The host provides language, persistence and navigation.
window.FlightdeckHelp = (() => {
  let host = null, dialog = null, topicId = 'flight', index = 0, mode = 'tour';
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const locale = () => host?.language() === 'en' ? 'en' : 'fr';
  const text = (fr, en) => locale() === 'en' ? en : fr;
  const content = () => window.FLIGHTDECK_HELP;
  const selected = () => content().topics.find(row => row.id === topicId) || content().topics[0];
  function close() {
    if (!dialog) return;
    const old = dialog; dialog = null; old.close(); old.remove();
    host?.seen();
  }
  function render() {
    const row = selected(), step = row.steps[index], lang = locale();
    dialog.innerHTML = `<div class="fd-help-head"><span>✈ RFS FLIGHTDECK</span><button data-help="close" aria-label="${text('Fermer l’aide','Close help')}">×</button></div>
      <h2 id="fd-help-title">${text('Votre cockpit, à votre rythme','Your cockpit, at your pace')}</h2>
      ${host?.prototype ? `<p class="fd-help-note">${text('Prototype web : les fonctions avancées décrites ici concernent les applications PC et Android. Les rubriques disponibles s’ouvrent avec Essayer.','Web prototype: advanced features described here belong to the PC and Android apps. Try opens available sections.')}</p>` : ''}
      <div class="fd-help-actions"><button data-help="tour" aria-pressed="${mode === 'tour'}">${text('Tutoriel','Tutorial')}</button><button data-help="faq" aria-pressed="${mode === 'faq'}">${text('30 questions fréquentes','30 frequently asked questions')}</button></div>
      ${mode === 'tour' ? `<label for="fd-help-topic">${text('La rubrique qui vous intéresse','Choose a section')}</label><select id="fd-help-topic">${content().topics.map(v => `<option value="${v.id}" ${v.id === row.id ? 'selected' : ''}>${escape(v.title[lang])}</option>`).join('')}</select>
      <div class="fd-help-step"><p class="fd-help-progress">${index+1} / ${row.steps.length} · ${escape(row.title[lang])}</p><h3>${escape(step.title[lang])}</h3><p>${escape(step.text[lang])}</p></div>
      <div class="fd-help-actions"><button data-help="previous" ${index === 0 ? 'disabled' : ''}>${text('Précédent','Previous')}</button><button data-help="next" ${index === row.steps.length-1 ? 'disabled' : ''}>${text('Suivant','Next')}</button><button data-help="try">${text('Essayer','Try')}</button></div>` : `<label for="fd-help-search">${text('Rechercher une question','Search for a question')}</label><input id="fd-help-search" type="search" autocomplete="off" placeholder="${text('Installation, ETE, carburant…','Installation, ETE, fuel…')}"><p id="fd-help-count" role="status">30 / 30</p><div id="fd-help-faq">${content().faq.map(v => `<details data-faq="${v.id}"><summary>${escape(v.question[lang])}</summary><p>${escape(v.answer[lang])}</p></details>`).join('')}</div>`}
      <button class="fd-help-skip" data-help="close">${text('Passer / revenir à l’application','Skip / return to the app')}</button>
      <p class="fd-help-note">${text('Vous pourrez retrouver cette aide à tout moment. Rien ne sera effacé.','You can reopen this help at any time. Nothing will be erased.')}</p>`;
    dialog.querySelector('[data-help="' + mode + '"]').focus({preventScroll:true});
  }
  function open(topic = 'flight', section = 'tour') {
    if (!host || !content()) return;
    if (dialog) { dialog.focus(); return; }
    topicId = topic; index = 0; mode = section;
    dialog = document.createElement('dialog'); dialog.className = 'fd-help';
    const opened = dialog;
    opened.addEventListener('close', () => {
      // Android Back also closes native HTML dialogs through the host.
      if (dialog === opened) { dialog = null; opened.remove(); host?.seen(); }
    });
    dialog.setAttribute('aria-labelledby', 'fd-help-title');
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
    dialog.addEventListener('click', event => {
      const action = event.target.closest('[data-help]')?.dataset.help;
      if (!action) return;
      if (action === 'close') return close();
      if (action === 'try') { const row = selected(), target = row.steps[index].target; close(); host.navigate(row.id, target); return; }
      if (action === 'tour' || action === 'faq') mode = action;
      if (action === 'next') index = Math.min(selected().steps.length-1, index+1);
      if (action === 'previous') index = Math.max(0, index-1);
      render();
    });
    dialog.addEventListener('change', event => {
      if (event.target.id === 'fd-help-topic') { topicId = event.target.value; index = 0; render(); }
    });
    dialog.addEventListener('input', event => {
      if (event.target.id !== 'fd-help-search') return;
      const query = event.target.value.trim().toLocaleLowerCase(locale()); let count = 0;
      dialog.querySelectorAll('[data-faq]').forEach(el => { el.hidden = !el.textContent.toLocaleLowerCase(locale()).includes(query); if (!el.hidden) count++; });
      dialog.querySelector('#fd-help-count').textContent = `${count} / 30`;
    });
    document.body.append(dialog); render(); dialog.showModal();
  }
  return {init(config) {host = config;}, open, close, maybeOffer() {if (host && !host.hasSeen()) open('flight');}};
})();
