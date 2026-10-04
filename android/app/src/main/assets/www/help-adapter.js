'use strict';
FlightdeckHelp.init({language:()=>model?.state.language, hasSeen:()=>!!model?.state.tutorial_seen,
  seen:()=>{if(!model)return; model.state.tutorial_seen=true; rpc('save',stateArgs()).catch(fail);},
  navigate:async(topic,target)=>{await navigate(topic);focusHelpTarget(target);}
});
function focusHelpTarget(key) {
  if(!key)return;
  const el=document.querySelector(`[data-key="${CSS.escape(key)}"]`);
  if(!el)return;
  for(let parent=el.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS')parent.open=true;
  el.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'auto':'smooth'});
  el.focus({preventScroll:true}); el.classList.add('issue-target');
  setTimeout(()=>el.classList.remove('issue-target'),1800);
}
const helpBasePaint=paint;
paint=()=>{
  helpBasePaint();
  if(screen==='welcome')return;
  const button=document.createElement('button');button.dataset.helpTopic=screen;
  button.className='context-help';button.textContent=t('Comprendre cet écran','Understand this screen');
  const title=$('content').querySelector('h1');if(title)title.after(button);
  if(screen==='settings')$('content').insertAdjacentHTML('beforeend',`<section class="card"><h2>${t('Aide à bord','Onboard help')}</h2><div class="actions"><button data-help-topic="flight">${t('Revoir le tutoriel','Replay tutorial')}</button><button data-help-topic="settings" data-help-mode="faq">${t('30 questions fréquentes','30 frequently asked questions')}</button></div></section>`);
  if(screen==='flight'&&model.state.intro_seen)FlightdeckHelp.maybeOffer();
};
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-help-topic]');
  if(button)FlightdeckHelp.open(button.dataset.helpTopic,button.dataset.helpMode||'tour');
  const issue=event.target.closest('[data-issue-index]');
  if(!issue)return;
  const key=rendered.issues[Number(issue.dataset.issueIndex)]?.field;if(!key)return;
  if(['length','emoji','design'].includes(key)){await navigate(key==='design'?'messages':'preview');focusHelpTarget(key==='design'?'design':'');if(key!=='design')$('preview')?.focus();}
  else {await navigate(meta.flight_fields[key]||key==='pilots'?'flight':'messages');focusHelpTarget(key==='pilots'?'name':key);}
});
