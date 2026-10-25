(ns jp-go-dds.behavior
  "The headless behavior layer — what Radix is to shadcn — for DADS markup.

  DADS upstream is CSS and example HTML; the behaviours its examples rely on
  (a menu-list-box that opens, a tab that switches, a dialog that returns
  focus) live in per-component scripts upstream and, in this workspace, were
  re-written per pattern (the shell's account menu, the switch). Measured
  2026-09-16: no shared focus management, keyboard navigation or ARIA
  wiring existed, so every new screen grew a script of its own.

  `script` is ONE dependency-free, idempotent runtime (a host ships it as a
  file — script-src 'self' hosts cannot inline it; `<script src=…
  defer>`). Every behaviour is delegated on `document` and keyed by a
  marker on the markup, never by class name — the same way
  shinkansen.audit's :chrome-layers reads `data-chrome`:

    data-behavior=\"dialog\"      <dialog>: showModal() is the platform's focus
                               trap, Escape and focus return are the
                               platform's; this adds the invoker attributes
                               (command / commandfor) where the browser
                               lacks them, data-dialog-open / -close, and
                               the backdrop-click policy (no action unless
                               data-backdrop-click=\"close\")
    data-behavior=\"menu\"        [data-menu-opener][aria-expanded] +
                               [data-menu-popup][data-chrome=float] of
                               role=menuitem — click / ArrowDown opens,
                               Escape closes and refocuses the opener,
                               outside click / focus closes, Arrow / Home /
                               End / typeahead move, an item click closes
    data-behavior=\"tabs\"        [role=tablist] > [role=tab] + [role=tabpanel]
                               — automatic activation, roving tabindex,
                               arrows by aria-orientation, panels hidden
    data-behavior=\"disclosure\"  a control with aria-expanded + aria-controls
                               that shows / hides its target (a <details>
                               needs nothing — this is the hamburger, the
                               show-more)
    data-behavior=\"radiogroup\"  [role=radio] controls — arrows move AND
                               choose (they click), roving tabindex follows
                               aria-checked; what choosing does stays the
                               host's click handler
    data-behavior=\"toast\"       the live region; jpGoDds.behavior.toast({text,
                               actionLabel, onAction, timeout, tone}) appends
                               a .dds-ext-toast that dismisses itself after
                               timeout ms (0 = stays), pauses while hovered
                               or focused, closes on Escape / its button
    data-behavior=\"combobox\"    input[role=combobox] + [role=listbox] of
                               [role=option][data-value] — filters as typed,
                               arrows move aria-activedescendant, Enter
                               chooses (value → root data-value, the
                               [data-combobox-value] hidden input, a change
                               event), Escape / outside closes

    data-behavior=\"popover\"     [data-popover-opener][aria-expanded][aria-
                               controls] + [data-popover-panel][data-chrome=
                               float][hidden] — non-modal: click toggles,
                               Escape closes and refocuses the opener,
                               outside click / focus-out closes;
                               data-popover-focus moves focus in on open
    data-behavior=\"tooltip\"     a trigger [aria-describedby] + [role=tooltip]
                               [hidden] — shows after data-delay ms (300)
                               on hover or focus, hides on leave / blur /
                               Escape; above, below when there is no room
    data-behavior=\"select\"      button[role=combobox][aria-haspopup=listbox]
                               [aria-expanded][aria-controls] + [role=
                               listbox][data-chrome=float][hidden] of
                               [role=option][data-value] (APG select-only
                               combobox) — arrows open and move, Enter /
                               Space choose, Escape closes, typeahead,
                               Home / End; value → root data-value,
                               [data-select-value], a change event
    data-behavior=\"slider\"      [data-slider-track] + [role=slider][aria-
                               valuemin][aria-valuemax][aria-valuenow] —
                               arrows ± data-step (1), PageUp / PageDown ±
                               10 steps, Home / End, pointer drag on the
                               track; value → aria-valuenow, --slider-value
                               (percent, the track fill), [data-slider-
                               value], input / change events

    data-behavior=\"table\"       a .dads-table root: th[aria-sort] > button
                               sorts the tbody by that column (text, or
                               data-sort-value; numeric when both sides
                               parse), toggling ascending / descending,
                               aria-sort on the active header only;
                               [data-table-filter] (an input) hides rows
                               that do not contain the text, [data-table-
                               count] shows visible / total. No
                               virtualisation — a DADS table is a page of
                               rows, not ten thousand

  Placement is collision-aware without a library (2026-09-16): every
  floating popup (menu, combobox, popover, select) is placed on open —
  flipped above its anchor when it would leave the viewport below and
  there is more room above (data-placement=up), and clamped horizontally
  with a translateX so it never runs off either edge; a tooltip prefers
  above and flips below (data-placement=down). `place(popup, anchor)` is
  exported for a host's own float.

  `css` carries the layer rules the markers need (a popup floats:
  position:absolute + z-index:var(--hig-z-float) — the rule :chrome-layers
  measures; the toast region is fixed at var(--hig-z-toast); [hidden] wins
  over a component's own display) on the --hig-* token contract with DADS
  primitives as fallbacks — no colour literal. Motion uses
  --hig-motion-* and stops under prefers-reduced-motion.

  Exposed as globalThis.jpGoDds.behavior: hydrate(root) for content added
  after load (tabs / radiogroups initialise, server-rendered toasts arm),
  toast(opts), openDialog / closeDialog, openMenu / closeMenu, selectTab.

  Both the markup half (jp-go-dds.core: modal-dialog, drawer, menu-list-box,
  tab, combobox, toast-region, …) and this script are measured in a real
  browser by test/behavior_browser_test.cljk; the string tests below pin
  the markers so a rename cannot slip past.

  The language selector keeps its own script (below): it predates this
  layer and 600+ documents ship it; it will fold into `menu` when its
  host markup moves."
  (:require [kotoba.lang.text :as str]))

(def markers
  "The behaviours this runtime answers, by their data-behavior value, with
   the markup each one needs — data, so a test or an audit can read it."
  {"dialog"     {:root "dialog[data-behavior=dialog]" :needs ["aria-labelledby"]}
   "menu"       {:root "[data-behavior=menu]"
                 :needs ["[data-menu-opener][aria-expanded][aria-controls]"
                         "[data-menu-popup][data-chrome=float][hidden]"]}
   "tabs"       {:root "[data-behavior=tabs]"
                 :needs ["[role=tablist]" "[role=tab][aria-selected]" "[role=tabpanel]"]}
   "disclosure" {:root "[data-behavior=disclosure]" :needs ["aria-expanded" "aria-controls"]}
   "radiogroup" {:root "[data-behavior=radiogroup][role=radiogroup]" :needs ["[role=radio][aria-checked]"]}
   "toast"      {:root "[data-behavior=toast][role=status][aria-live]" :needs []}
   "combobox"   {:root "[data-behavior=combobox]"
                 :needs ["[role=combobox][aria-expanded][aria-controls][aria-autocomplete]"
                         "[role=listbox][data-chrome=float]"]}
   "popover"    {:root "[data-behavior=popover]"
                 :needs ["[data-popover-opener][aria-expanded][aria-controls]"
                         "[data-popover-panel][data-chrome=float][hidden]"]}
   "tooltip"    {:root "[data-behavior=tooltip]"
                 :needs ["[aria-describedby]" "[role=tooltip][hidden]"]}
   "select"     {:root "[data-behavior=select]"
                 :needs ["[role=combobox][aria-haspopup=listbox][aria-expanded][aria-controls]"
                         "[role=listbox][data-chrome=float][hidden]" "[role=option][data-value]"]}
   "slider"     {:root "[data-behavior=slider]"
                 :needs ["[role=slider][aria-valuemin][aria-valuemax][aria-valuenow]"]}
   "table"      {:root "[data-behavior=table]"
                 :needs ["table" "th[aria-sort] button, [data-table-filter]"]}})

(def script
  "The behavior runtime — see the namespace docstring. Ship as a file."
  "(()=>{'use strict';
if(globalThis.jpGoDds&&globalThis.jpGoDds.behavior)return;
const doc=document;
const FOCUSABLE='a[href],area[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),summary,[tabindex]:not([tabindex=\"-1\"]),[contenteditable=\"true\"]';
const visible=el=>!el.closest('[hidden]')&&el.getClientRects().length>0;
const focusables=root=>Array.from(root.querySelectorAll(FOCUSABLE)).filter(visible);
const normalize=s=>String(s||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toLocaleLowerCase().trim();
let seq=0;const ensureId=(el,prefix)=>{if(!el.id)el.id=prefix+'-'+(++seq);return el.id;};
const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
const commandsNative='command' in HTMLButtonElement.prototype;

/* ---- dialog: <dialog data-behavior=\"dialog\"> — showModal() is the focus trap, Escape and focus return are the platform's; this adds the invoker attributes (command/commandfor) where the browser lacks them, data-dialog-open / data-dialog-close, and backdrop-click policy (contracts.edn :settings-sheet :backdrop-click :no-action) */
const dialogOf=(target)=>{const id=target.getAttribute('commandfor')||target.getAttribute('data-dialog-open');return id?doc.getElementById(id):target.closest('dialog');};
const openDialog=(dialog,opener)=>{if(!dialog||dialog.open)return;dialog.__jpOpener=opener||doc.activeElement;dialog.showModal();const first=dialog.querySelector('[autofocus]')||focusables(dialog)[0];if(first&&doc.activeElement!==first)first.focus();};
const closeDialog=dialog=>{if(!dialog||!dialog.open)return;dialog.close();};
doc.addEventListener('click',e=>{
 const t=e.target.closest('[command][commandfor],[data-dialog-open],[data-dialog-close]');if(!t)return;
 if(t.hasAttribute('data-dialog-close')){const d=t.closest('dialog');if(d){e.preventDefault();closeDialog(d);}return;}
 if(t.hasAttribute('data-dialog-open')){e.preventDefault();openDialog(dialogOf(t),t);return;}
 if(commandsNative)return;
 const cmd=t.getAttribute('command');const d=dialogOf(t);if(!d||d.tagName!=='DIALOG')return;
 if(cmd==='show-modal'){e.preventDefault();openDialog(d,t);}else if(cmd==='show'){e.preventDefault();d.show();}else if(cmd==='close'){e.preventDefault();closeDialog(d);}
});
doc.addEventListener('close',e=>{const d=e.target;if(d.tagName!=='DIALOG')return;const o=d.__jpOpener;d.__jpOpener=null;if(o&&o.isConnected&&typeof o.focus==='function'&&!d.contains(o))o.focus();},true);
doc.addEventListener('click',e=>{const d=e.target;if(d.tagName==='DIALOG'&&d.open&&d.dataset.behavior==='dialog'&&d.dataset.backdropClick==='close'){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDialog(d);}});

/* ---- placement: flip a float above its anchor when it would leave the viewport below (and there is more room above), clamp it horizontally — collision-aware, no library. data-placement=up is what css keys on; the horizontal shift is a translateX so the author's inset rules stay */
const place=(popup,anchor)=>{if(!popup||!anchor)return;popup.removeAttribute('data-placement');popup.style.transform='';const gap=8;const a=anchor.getBoundingClientRect();const r=popup.getBoundingClientRect();const below=innerHeight-a.bottom,above=a.top;if(r.height+gap>below&&above>below)popup.setAttribute('data-placement','up');const r2=popup.getBoundingClientRect();let dx=0;if(r2.left<gap)dx=gap-r2.left;else if(r2.right>innerWidth-gap)dx=innerWidth-gap-r2.right;if(dx)popup.style.transform='translateX('+Math.round(dx)+'px)';};

/* ---- menu: [data-behavior=\"menu\"] > [data-menu-opener][aria-expanded] + [data-menu-popup][hidden] (the popup carries data-chrome=\"float\", the layer the audit measures) with [role=\"menuitem\"] items */
const menuParts=root=>({opener:root.querySelector('[data-menu-opener]'),popup:root.querySelector('[data-menu-popup]'),items:Array.from(root.querySelectorAll('[data-menu-popup] [role=\"menuitem\"],[data-menu-popup] [role=\"menuitemradio\"],[data-menu-popup] [role=\"menuitemcheckbox\"],[data-menu-popup] [data-menu-item]')).filter(visible)});
const menus=()=>Array.from(doc.querySelectorAll('[data-behavior=\"menu\"]'));
const closeMenu=(root,refocus)=>{const {opener,popup}=menuParts(root);if(!popup||popup.hidden)return;popup.hidden=true;if(opener)opener.setAttribute('aria-expanded','false');if(refocus&&opener)opener.focus({preventScroll:true});root.dispatchEvent(new CustomEvent('jp-go-dds:menu-close',{bubbles:true}));};
const openMenu=root=>{const {opener,popup,items}=menuParts(root);if(!popup)return;menus().forEach(o=>{if(o!==root&&!o.contains(root))closeMenu(o,false);});popup.hidden=false;if(opener)opener.setAttribute('aria-expanded','true');if(!root.hasAttribute('data-menu-placement'))place(popup,opener);const first=items.find(i=>i.getAttribute('aria-checked')==='true')||menuParts(root).items[0];if(first)first.focus({preventScroll:true});root.dispatchEvent(new CustomEvent('jp-go-dds:menu-open',{bubbles:true}));};
doc.addEventListener('click',e=>{
 const opener=e.target.closest('[data-menu-opener]');
 if(opener){const root=opener.closest('[data-behavior=\"menu\"]');if(root){e.preventDefault();opener.getAttribute('aria-expanded')==='true'?closeMenu(root,true):openMenu(root);return;}}
 menus().forEach(root=>{if(!root.contains(e.target))closeMenu(root,false);else if(e.target.closest('[data-menu-popup]')&&e.target.closest('[role=\"menuitem\"],[role=\"menuitemradio\"],[role=\"menuitemcheckbox\"],[data-menu-item]')&&!root.hasAttribute('data-menu-keep'))closeMenu(root,true);});
});
doc.addEventListener('focusin',e=>menus().forEach(root=>{if(!root.contains(e.target))closeMenu(root,false);}));
doc.addEventListener('keydown',e=>{
 const root=e.target.closest('[data-behavior=\"menu\"]');if(!root)return;const {opener,popup,items}=menuParts(root);
 if(e.key==='Escape'){if(popup&&!popup.hidden){e.preventDefault();closeMenu(root,true);}return;}
 if(e.target===opener&&(e.key==='ArrowDown'||e.key==='ArrowUp')&&popup&&popup.hidden){e.preventDefault();openMenu(root);return;}
 if(!popup||popup.hidden||!items.length)return;
 if(e.key==='Tab'){closeMenu(root,false);return;}
 const cur=items.indexOf(doc.activeElement);let next=null;
 if(e.key==='ArrowDown')next=(cur+1)%items.length;else if(e.key==='ArrowUp')next=cur<0?items.length-1:(cur-1+items.length)%items.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=items.length-1;
 else if(e.key.length===1&&/\\S/.test(e.key)){const k=normalize(e.key);const from=cur+1;for(let i=0;i<items.length;i++){const it=items[(from+i)%items.length];if(normalize(it.textContent).startsWith(k)){next=(from+i)%items.length;break;}}}
 if(next!==null){e.preventDefault();items[next].focus();}
});

/* ---- tabs: [data-behavior=\"tabs\"] with [role=\"tablist\"] > [role=\"tab\"] and [role=\"tabpanel\"] — automatic activation, roving tabindex, arrows by orientation */
const tabParts=root=>{const list=root.querySelector('[role=\"tablist\"]');return {list,tabs:list?Array.from(list.querySelectorAll('[role=\"tab\"]')):[]};};
const panelOf=tab=>{const id=tab.getAttribute('aria-controls')||(tab.getAttribute('href')||'').replace(/^#/,'');return id?doc.getElementById(id):null;};
const selectTab=(root,tab,focus)=>{const {tabs}=tabParts(root);tabs.forEach(t=>{const on=t===tab;t.setAttribute('aria-selected',on?'true':'false');t.setAttribute('tabindex',on?'0':'-1');const p=panelOf(t);if(p){p.hidden=!on;}});if(focus)tab.focus();root.dispatchEvent(new CustomEvent('jp-go-dds:tab-select',{bubbles:true,detail:{id:tab.id,panel:panelOf(tab)}}));};
const initTabs=root=>{const {list,tabs}=tabParts(root);if(!list||!tabs.length)return;tabs.forEach(t=>{const p=panelOf(t);if(p){ensureId(t,'tab');if(!t.hasAttribute('aria-controls'))t.setAttribute('aria-controls',p.id);if(!p.hasAttribute('aria-labelledby'))p.setAttribute('aria-labelledby',t.id);}});const sel=tabs.find(t=>t.getAttribute('aria-selected')==='true')||tabs.find(t=>t.hasAttribute('aria-current'))||tabs[0];selectTab(root,sel,false);};
doc.addEventListener('click',e=>{const tab=e.target.closest('[role=\"tab\"]');const root=tab&&tab.closest('[data-behavior=\"tabs\"]');if(!root)return;if(tab.tagName==='A'&&!root.hasAttribute('data-tabs-navigate'))e.preventDefault();selectTab(root,tab,false);});
doc.addEventListener('keydown',e=>{const tab=e.target.closest('[role=\"tab\"]');const root=tab&&tab.closest('[data-behavior=\"tabs\"]');if(!root)return;const {list,tabs}=tabParts(root);const vertical=list.getAttribute('aria-orientation')==='vertical';const prev=vertical?'ArrowUp':'ArrowLeft',next=vertical?'ArrowDown':'ArrowRight';const i=tabs.indexOf(tab);let n=null;if(e.key===next)n=(i+1)%tabs.length;else if(e.key===prev)n=(i-1+tabs.length)%tabs.length;else if(e.key==='Home')n=0;else if(e.key==='End')n=tabs.length-1;if(n!==null){e.preventDefault();selectTab(root,tabs[n],true);}});

/* ---- disclosure: a control [data-behavior=\"disclosure\"][aria-expanded][aria-controls] that shows or hides its target (a <details> already does this natively; this is for a hamburger opening a menu bar, a \"show more\") */
doc.addEventListener('click',e=>{const c=e.target.closest('[data-behavior=\"disclosure\"]');if(!c)return;const t=doc.getElementById(c.getAttribute('aria-controls')||'');if(!t)return;e.preventDefault();const open=c.getAttribute('aria-expanded')!=='true';c.setAttribute('aria-expanded',open?'true':'false');t.hidden=!open;if(open){const f=focusables(t)[0];if(f&&c.hasAttribute('data-disclosure-focus'))f.focus();}c.dispatchEvent(new CustomEvent('jp-go-dds:disclosure',{bubbles:true,detail:{open}}));});
doc.addEventListener('keydown',e=>{if(e.key!=='Escape')return;const t=e.target.closest('[id]');const c=t&&doc.querySelector('[data-behavior=\"disclosure\"][aria-expanded=\"true\"][aria-controls=\"'+t.id+'\"]');if(c){c.click();c.focus();}});

/* ---- radiogroup: [data-behavior=\"radiogroup\"] of [role=\"radio\"] controls — arrows move AND choose (click), roving tabindex follows aria-checked; what choosing does stays the host's click handler */
const radios=root=>Array.from(root.querySelectorAll('[role=\"radio\"]')).filter(visible);
const initRadiogroup=root=>{const rs=radios(root);if(!rs.length)return;const on=rs.find(r=>r.getAttribute('aria-checked')==='true')||rs[0];rs.forEach(r=>r.setAttribute('tabindex',r===on?'0':'-1'));};
doc.addEventListener('keydown',e=>{const r=e.target.closest('[role=\"radio\"]');const root=r&&r.closest('[data-behavior=\"radiogroup\"]');if(!root)return;const rs=radios(root);const i=rs.indexOf(r);let n=null;if(e.key==='ArrowRight'||e.key==='ArrowDown')n=(i+1)%rs.length;else if(e.key==='ArrowLeft'||e.key==='ArrowUp')n=(i-1+rs.length)%rs.length;else if(e.key==='Home')n=0;else if(e.key==='End')n=rs.length-1;else if(e.key===' '){e.preventDefault();r.click();return;}if(n===null)return;e.preventDefault();rs[n].focus();rs[n].click();});
doc.addEventListener('click',e=>{const r=e.target.closest('[role=\"radio\"]');const root=r&&r.closest('[data-behavior=\"radiogroup\"]');if(!root)return;radios(root).forEach(x=>x.setAttribute('tabindex',x===r?'0':'-1'));});

/* ---- toast: [data-behavior=\"toast\"] is the live region (role=\"status\" aria-live=\"polite\"); items are .dds-ext-toast, armed with data-timeout (ms, 0 = stays), paused while hovered or focused, dismissed by [data-toast-close] or Escape */
const toastRegion=()=>doc.querySelector('[data-behavior=\"toast\"]');
const dismissToast=item=>{if(!item||item.__jpDone)return;item.__jpDone=true;clearTimeout(item.__jpTimer);const inside=item.contains(doc.activeElement);item.setAttribute('data-leaving','');const gone=()=>{item.remove();if(inside&&item.__jpFrom&&item.__jpFrom.isConnected)item.__jpFrom.focus();item.dispatchEvent(new CustomEvent('jp-go-dds:toast-dismiss',{bubbles:true}));};if(reduced())gone();else setTimeout(gone,200);};
const armToast=item=>{const ms=Number(item.dataset.timeout==null?6000:item.dataset.timeout);if(item.__jpArmed)return;item.__jpArmed=true;item.__jpFrom=doc.activeElement;if(ms>0){const start=()=>{clearTimeout(item.__jpTimer);item.__jpTimer=setTimeout(()=>dismissToast(item),ms);};const stop=()=>clearTimeout(item.__jpTimer);item.addEventListener('mouseenter',stop);item.addEventListener('mouseleave',start);item.addEventListener('focusin',stop);item.addEventListener('focusout',start);start();}};
const toast=(opts)=>{opts=opts||{};const region=opts.region||toastRegion();if(!region)return null;const item=doc.createElement('div');item.className='dds-ext-toast';if(opts.tone)item.dataset.tone=opts.tone;item.dataset.timeout=String(opts.timeout==null?6000:opts.timeout);const text=doc.createElement('p');text.className='dds-ext-toast__text';text.textContent=String(opts.text||'');item.appendChild(text);if(opts.actionLabel){const b=doc.createElement('button');b.type='button';b.className='dds-ext-toast__action';b.textContent=opts.actionLabel;b.addEventListener('click',()=>{if(typeof opts.onAction==='function')opts.onAction();dismissToast(item);});item.appendChild(b);}const c=doc.createElement('button');c.type='button';c.className='dds-ext-toast__close';c.setAttribute('data-toast-close','');c.setAttribute('aria-label',opts.closeLabel||region.dataset.closeLabel||'閉じる');c.textContent='×';item.appendChild(c);region.appendChild(item);armToast(item);return item;};
doc.addEventListener('click',e=>{const c=e.target.closest('[data-toast-close]');if(c)dismissToast(c.closest('.dds-ext-toast'));});
doc.addEventListener('keydown',e=>{if(e.key!=='Escape')return;const item=e.target.closest('.dds-ext-toast');if(item){e.preventDefault();dismissToast(item);}});

/* ---- combobox: [data-behavior=\"combobox\"] > input[role=\"combobox\"][aria-controls] + [role=\"listbox\"][hidden] of [role=\"option\"][data-value] — filter as typed, arrows move aria-activedescendant, Enter chooses, Escape closes; the chosen value lands on the root (data-value), on [data-combobox-value] (a hidden input for the form) and as a change event */
const cbParts=root=>({input:root.querySelector('[role=\"combobox\"]'),list:root.querySelector('[role=\"listbox\"]'),options:Array.from(root.querySelectorAll('[role=\"option\"]')),empty:root.querySelector('[data-combobox-empty]'),value:root.querySelector('[data-combobox-value]')});
const cbVisible=root=>cbParts(root).options.filter(o=>!o.hidden&&!(o.parentElement&&o.parentElement.hidden));
const cbSetActive=(root,opt)=>{const {input,options}=cbParts(root);options.forEach(o=>o.setAttribute('aria-selected',o===opt?'true':'false'));if(opt){ensureId(opt,'option');input.setAttribute('aria-activedescendant',opt.id);if(opt.scrollIntoView)opt.scrollIntoView({block:'nearest'});}else input.removeAttribute('aria-activedescendant');};
const cbOpen=root=>{const {input,list}=cbParts(root);if(!list)return;list.hidden=false;input.setAttribute('aria-expanded','true');place(list,input);};
const cbClose=root=>{const {input,list}=cbParts(root);if(!list||list.hidden)return;list.hidden=true;input.setAttribute('aria-expanded','false');cbSetActive(root,null);};
const cbFilter=root=>{const {input,options,empty}=cbParts(root);const term=normalize(input.value);let n=0;options.forEach(o=>{const hay=normalize(o.dataset.comboboxKeywords||o.textContent);const show=!term||hay.includes(term);const li=o.parentElement&&o.parentElement.tagName==='LI'?o.parentElement:o;li.hidden=!show;if(show)n++;});if(empty)empty.hidden=n>0;return n;};
const cbChoose=(root,opt)=>{const {input,value}=cbParts(root);const label=opt.dataset.label||opt.textContent.trim();const v=opt.dataset.value!=null?opt.dataset.value:label;input.value=label;root.dataset.value=v;if(value)value.value=v;cbClose(root);input.dispatchEvent(new Event('change',{bubbles:true}));root.dispatchEvent(new CustomEvent('jp-go-dds:combobox-choose',{bubbles:true,detail:{value:v,label}}));};
doc.addEventListener('input',e=>{const root=e.target.closest('[data-behavior=\"combobox\"]');if(!root||e.target.getAttribute('role')!=='combobox')return;cbFilter(root);cbOpen(root);cbSetActive(root,null);if(root.dataset.value!=null){delete root.dataset.value;const {value}=cbParts(root);if(value)value.value='';}});
doc.addEventListener('click',e=>{const opt=e.target.closest('[role=\"option\"]');const root=e.target.closest('[data-behavior=\"combobox\"]');if(opt&&root){e.preventDefault();cbChoose(root,opt);return;}const trigger=e.target.closest('[data-combobox-toggle]');if(trigger&&root){const {list,input}=cbParts(root);list&&list.hidden?(cbFilter(root),cbOpen(root),input.focus()):cbClose(root);return;}doc.querySelectorAll('[data-behavior=\"combobox\"]').forEach(r=>{if(!r.contains(e.target))cbClose(r);});});
doc.addEventListener('focusin',e=>doc.querySelectorAll('[data-behavior=\"combobox\"]').forEach(r=>{if(!r.contains(e.target))cbClose(r);}));
doc.addEventListener('keydown',e=>{const root=e.target.closest('[data-behavior=\"combobox\"]');if(!root||e.target.getAttribute('role')!=='combobox')return;const {list}=cbParts(root);const opts=cbVisible(root);const cur=opts.findIndex(o=>o.getAttribute('aria-selected')==='true');
 if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(list&&list.hidden){cbFilter(root);cbOpen(root);}const vis=cbVisible(root);if(!vis.length)return;const n=e.key==='ArrowDown'?(cur+1)%vis.length:cur<0?vis.length-1:(cur-1+vis.length)%vis.length;cbSetActive(root,vis[n]);return;}
 if(e.key==='Home'||e.key==='End'){if(list&&!list.hidden&&opts.length){e.preventDefault();cbSetActive(root,opts[e.key==='Home'?0:opts.length-1]);}return;}
 if(e.key==='Enter'){if(list&&!list.hidden&&cur>=0){e.preventDefault();cbChoose(root,opts[cur]);}return;}
 if(e.key==='Escape'){if(list&&!list.hidden){e.preventDefault();cbClose(root);}return;}
 if(e.key==='Tab')cbClose(root);
});

/* ---- popover: [data-behavior=\"popover\"] > [data-popover-opener][aria-expanded][aria-controls] + [data-popover-panel][data-chrome=\"float\"][hidden] — non-modal: click toggles, Escape closes and refocuses the opener, outside click / focus-out closes, placement flips and clamps; data-popover-focus on the root moves focus into the panel on open */
const popParts=root=>({opener:root.querySelector('[data-popover-opener]'),panel:root.querySelector('[data-popover-panel]')});
const popovers=()=>Array.from(doc.querySelectorAll('[data-behavior=\"popover\"]'));
const closePopover=(root,refocus)=>{const {opener,panel}=popParts(root);if(!panel||panel.hidden)return;panel.hidden=true;if(opener)opener.setAttribute('aria-expanded','false');if(refocus&&opener)opener.focus({preventScroll:true});root.dispatchEvent(new CustomEvent('jp-go-dds:popover-close',{bubbles:true}));};
const openPopover=root=>{const {opener,panel}=popParts(root);if(!panel)return;popovers().forEach(o=>{if(o!==root&&!o.contains(root))closePopover(o,false);});panel.hidden=false;if(opener)opener.setAttribute('aria-expanded','true');place(panel,opener);if(root.hasAttribute('data-popover-focus')){const f=focusables(panel)[0];if(f)f.focus({preventScroll:true});}root.dispatchEvent(new CustomEvent('jp-go-dds:popover-open',{bubbles:true}));};
doc.addEventListener('click',e=>{const opener=e.target.closest('[data-popover-opener]');if(opener){const root=opener.closest('[data-behavior=\"popover\"]');if(root){e.preventDefault();opener.getAttribute('aria-expanded')==='true'?closePopover(root,true):openPopover(root);return;}}popovers().forEach(root=>{if(!root.contains(e.target))closePopover(root,false);});});
doc.addEventListener('focusin',e=>popovers().forEach(root=>{if(!root.contains(e.target))closePopover(root,false);}));
doc.addEventListener('keydown',e=>{if(e.key!=='Escape')return;const root=e.target.closest('[data-behavior=\"popover\"]');if(!root)return;const {panel}=popParts(root);if(panel&&!panel.hidden){e.preventDefault();closePopover(root,true);}});

/* ---- tooltip: [data-behavior=\"tooltip\"] > a trigger [aria-describedby] + [role=\"tooltip\"][hidden] — shows after data-delay ms (300) on hover or focus, hides on leave / blur / Escape; above the trigger, below (data-placement=down) when there is no room, clamped horizontally */
const tipParts=root=>({trigger:root.querySelector('[aria-describedby]'),tip:root.querySelector('[role=\"tooltip\"]')});
const showTip=root=>{const {trigger,tip}=tipParts(root);if(!tip||!trigger||!tip.hidden)return;tip.hidden=false;tip.removeAttribute('data-placement');tip.style.transform='';const gap=8;const a=trigger.getBoundingClientRect(),r=tip.getBoundingClientRect();if(a.top<r.height+gap&&innerHeight-a.bottom>a.top)tip.setAttribute('data-placement','down');const r2=tip.getBoundingClientRect();let dx=0;if(r2.left<gap)dx=gap-r2.left;else if(r2.right>innerWidth-gap)dx=innerWidth-gap-r2.right;if(dx)tip.style.transform='translateX('+Math.round(dx)+'px)';};
const hideTip=root=>{const {tip}=tipParts(root);if(tip&&!tip.hidden)tip.hidden=true;};
const armTooltip=root=>{const {trigger}=tipParts(root);if(!trigger||trigger.__jpTip)return;trigger.__jpTip=true;const ms=Number(root.dataset.delay==null?300:root.dataset.delay);let t=null;const open=()=>{clearTimeout(t);t=setTimeout(()=>showTip(root),ms);};const close=()=>{clearTimeout(t);hideTip(root);};trigger.addEventListener('mouseenter',open);trigger.addEventListener('mouseleave',close);trigger.addEventListener('focus',open);trigger.addEventListener('blur',close);};
doc.addEventListener('keydown',e=>{if(e.key!=='Escape')return;doc.querySelectorAll('[data-behavior=\"tooltip\"]').forEach(hideTip);});

/* ---- select: [data-behavior=\"select\"] > button[role=\"combobox\"][aria-haspopup=\"listbox\"][aria-controls] + [role=\"listbox\"][hidden] of [role=\"option\"][data-value] (APG select-only combobox) — arrows open and move aria-activedescendant, Enter / Space choose, Escape closes, typeahead, Home / End; the value lands on the root (data-value), on [data-select-value] (a hidden input) and as a change event; [data-select-label] is the text the button shows */
const selParts=root=>({button:root.querySelector('[role=\"combobox\"]'),list:root.querySelector('[role=\"listbox\"]'),options:Array.from(root.querySelectorAll('[role=\"option\"]')).filter(o=>!o.hasAttribute('aria-disabled')),value:root.querySelector('[data-select-value]'),label:root.querySelector('[data-select-label]')});
const selSetActive=(root,opt)=>{const {button,options}=selParts(root);options.forEach(o=>o.setAttribute('aria-selected',o===opt?'true':'false'));if(opt){ensureId(opt,'option');button.setAttribute('aria-activedescendant',opt.id);if(opt.scrollIntoView)opt.scrollIntoView({block:'nearest'});}else button.removeAttribute('aria-activedescendant');};
const selClose=root=>{const {button,list}=selParts(root);if(!list||list.hidden)return;list.hidden=true;button.setAttribute('aria-expanded','false');button.removeAttribute('aria-activedescendant');};
const selOpen=root=>{const {button,list,options}=selParts(root);if(!list)return;doc.querySelectorAll('[data-behavior=\"select\"]').forEach(o=>{if(o!==root)selClose(o);});list.hidden=false;button.setAttribute('aria-expanded','true');place(list,button);const cur=options.find(o=>o.dataset.value===root.dataset.value)||options[0];selSetActive(root,cur);};
const selChoose=(root,opt)=>{const {button,value,label,options}=selParts(root);const text=opt.dataset.label||opt.textContent.trim();const v=opt.dataset.value!=null?opt.dataset.value:text;(label||button).textContent=text;root.dataset.value=v;if(value)value.value=v;options.forEach(o=>o.setAttribute('aria-selected',o===opt?'true':'false'));selClose(root);button.focus({preventScroll:true});root.dispatchEvent(new CustomEvent('jp-go-dds:select-choose',{bubbles:true,detail:{value:v,label:text}}));if(value)value.dispatchEvent(new Event('change',{bubbles:true}));};
doc.addEventListener('click',e=>{const root=e.target.closest('[data-behavior=\"select\"]');const opt=e.target.closest('[role=\"option\"]');if(root&&opt&&root.contains(opt)){e.preventDefault();selChoose(root,opt);return;}const b=e.target.closest('[data-behavior=\"select\"] [role=\"combobox\"]');if(b){const r=b.closest('[data-behavior=\"select\"]');e.preventDefault();selParts(r).list&&selParts(r).list.hidden?selOpen(r):selClose(r);return;}doc.querySelectorAll('[data-behavior=\"select\"]').forEach(r=>{if(!r.contains(e.target))selClose(r);});});
doc.addEventListener('focusin',e=>doc.querySelectorAll('[data-behavior=\"select\"]').forEach(r=>{if(!r.contains(e.target))selClose(r);}));
doc.addEventListener('keydown',e=>{const b=e.target.closest('[data-behavior=\"select\"] [role=\"combobox\"]');if(!b)return;const root=b.closest('[data-behavior=\"select\"]');const {list,options}=selParts(root);const open=list&&!list.hidden;const cur=options.findIndex(o=>o.getAttribute('aria-selected')==='true');
 if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(!open){selOpen(root);return;}if(!options.length)return;const n=e.key==='ArrowDown'?Math.min(cur+1,options.length-1):Math.max(cur-1,0);selSetActive(root,options[n]);return;}
 if(e.key==='Home'||e.key==='End'){if(open&&options.length){e.preventDefault();selSetActive(root,options[e.key==='Home'?0:options.length-1]);}return;}
 if(e.key==='Enter'||e.key===' '){e.preventDefault();if(open){if(cur>=0)selChoose(root,options[cur]);else selClose(root);}else selOpen(root);return;}
 if(e.key==='Escape'){if(open){e.preventDefault();selClose(root);}return;}
 if(e.key==='Tab'){selClose(root);return;}
 if(e.key.length===1&&/\\S/.test(e.key)){const k=normalize(e.key);const from=cur+1;for(let i=0;i<options.length;i++){const o=options[(from+i)%options.length];if(normalize(o.textContent).startsWith(k)){e.preventDefault();if(open)selSetActive(root,o);else selChoose(root,o);break;}}}
});

/* ---- slider: [data-behavior=\"slider\"] > [data-slider-track] + [role=\"slider\"][aria-valuemin][aria-valuemax][aria-valuenow] — arrows ± data-step (1), PageUp / PageDown ± 10 steps, Home / End; pointer drag on the track (pointer capture on document); the value lands on aria-valuenow, --slider-value (percent, the track fill), [data-slider-value] (a hidden input), [data-slider-output] (text) and as jp-go-dds:slider-input / -change (+ a change event on the input) */
const slParts=root=>({thumb:root.querySelector('[role=\"slider\"]'),track:root.querySelector('[data-slider-track]')||root,value:root.querySelector('[data-slider-value]'),out:root.querySelector('[data-slider-output]')});
const slNum=(el,a,d)=>{const v=Number(el.getAttribute(a));return isNaN(v)?d:v;};
const slSet=(root,v,commit)=>{const {thumb,value,out}=slParts(root);if(!thumb)return;const min=slNum(thumb,'aria-valuemin',0),max=slNum(thumb,'aria-valuemax',100),step=Number(root.dataset.step||1)||1;v=Math.min(max,Math.max(min,Math.round((v-min)/step)*step+min));v=Number(v.toFixed(6));const pct=max>min?((v-min)/(max-min))*100:0;thumb.setAttribute('aria-valuenow',String(v));root.style.setProperty('--slider-value',pct+'%');if(value)value.value=String(v);if(out)out.textContent=String(v);root.dispatchEvent(new CustomEvent('jp-go-dds:slider-input',{bubbles:true,detail:{value:v}}));if(commit){if(value)value.dispatchEvent(new Event('change',{bubbles:true}));root.dispatchEvent(new CustomEvent('jp-go-dds:slider-change',{bubbles:true,detail:{value:v}}));}};
const initSlider=root=>{const {thumb}=slParts(root);if(!thumb||root.__jpSlider)return;root.__jpSlider=true;if(!thumb.hasAttribute('tabindex'))thumb.setAttribute('tabindex','0');slSet(root,slNum(thumb,'aria-valuenow',slNum(thumb,'aria-valuemin',0)),false);};
const slFromPointer=(root,e)=>{const {thumb,track}=slParts(root);const r=track.getBoundingClientRect();const min=slNum(thumb,'aria-valuemin',0),max=slNum(thumb,'aria-valuemax',100);const x=Math.min(r.right,Math.max(r.left,e.clientX));const frac=r.width?(x-r.left)/r.width:0;const rtl=getComputedStyle(root).direction==='rtl';return min+(rtl?1-frac:frac)*(max-min);};
doc.addEventListener('pointerdown',e=>{const root=e.target.closest('[data-behavior=\"slider\"]');if(!root||e.button!==0)return;const {thumb,track}=slParts(root);if(!thumb||(!track.contains(e.target)&&e.target!==thumb))return;e.preventDefault();slSet(root,slFromPointer(root,e),false);thumb.focus({preventScroll:true});const move=ev=>slSet(root,slFromPointer(root,ev),false);const up=ev=>{doc.removeEventListener('pointermove',move);doc.removeEventListener('pointerup',up);doc.removeEventListener('pointercancel',up);slSet(root,slFromPointer(root,ev),true);};doc.addEventListener('pointermove',move);doc.addEventListener('pointerup',up);doc.addEventListener('pointercancel',up);});
doc.addEventListener('keydown',e=>{const thumb=e.target.closest('[role=\"slider\"]');const root=thumb&&thumb.closest('[data-behavior=\"slider\"]');if(!root)return;const min=slNum(thumb,'aria-valuemin',0),max=slNum(thumb,'aria-valuemax',100),step=Number(root.dataset.step||1)||1,cur=slNum(thumb,'aria-valuenow',min);let v=null;if(e.key==='ArrowRight'||e.key==='ArrowUp')v=cur+step;else if(e.key==='ArrowLeft'||e.key==='ArrowDown')v=cur-step;else if(e.key==='PageUp')v=cur+step*10;else if(e.key==='PageDown')v=cur-step*10;else if(e.key==='Home')v=min;else if(e.key==='End')v=max;if(v!==null){e.preventDefault();slSet(root,v,true);}});

/* ---- table: [data-behavior=\"table\"] > table with th[aria-sort] > button (sort by that column, ascending then descending; data-sort-value overrides the cell text; numeric when both parse) and an optional [data-table-filter] input (rows that do not contain the text are hidden; [data-table-count] shows visible / total) */
const tblParts=root=>({table:root.querySelector('table'),body:root.querySelector('tbody'),filter:root.querySelector('[data-table-filter]'),count:root.querySelector('[data-table-count]')});
const tblRows=root=>{const {body}=tblParts(root);return body?Array.from(body.querySelectorAll(':scope > tr')):[];};
const tblKey=(row,i)=>{const cell=row.children[i];if(!cell)return '';return cell.dataset.sortValue!=null?cell.dataset.sortValue:cell.textContent.trim();};
const tblSort=(root,th,dir)=>{const {table,body}=tblParts(root);if(!table||!body)return;const ths=Array.from(table.querySelectorAll('thead th'));const i=ths.indexOf(th);if(i<0)return;const rows=tblRows(root);const nums=rows.every(r=>tblKey(r,i)===''||!isNaN(parseFloat(tblKey(r,i))));const cmp=(a,b)=>{const ka=tblKey(a,i),kb=tblKey(b,i);const c=nums?(parseFloat(ka)||0)-(parseFloat(kb)||0):ka.localeCompare(kb,undefined,{numeric:true,sensitivity:'base'});return dir==='descending'?-c:c;};rows.map((r,n)=>[r,n]).sort((a,b)=>cmp(a[0],b[0])||a[1]-b[1]).forEach(([r])=>body.appendChild(r));ths.forEach(t=>{if(t.hasAttribute('aria-sort'))t.setAttribute('aria-sort',t===th?dir:'none');});root.dispatchEvent(new CustomEvent('jp-go-dds:table-sort',{bubbles:true,detail:{column:i,direction:dir}}));};
const tblFilter=root=>{const {filter,count}=tblParts(root);const term=normalize(filter?filter.value:'');const rows=tblRows(root);let n=0;rows.forEach(r=>{const show=!term||normalize(r.textContent).includes(term);r.hidden=!show;if(show)n++;});if(count)count.textContent=n+' / '+rows.length;root.dispatchEvent(new CustomEvent('jp-go-dds:table-filter',{bubbles:true,detail:{visible:n,total:rows.length}}));};
doc.addEventListener('click',e=>{const b=e.target.closest('th[aria-sort] button');const root=b&&b.closest('[data-behavior=\"table\"]');if(!root)return;e.preventDefault();const th=b.closest('th');const cur=th.getAttribute('aria-sort');tblSort(root,th,cur==='ascending'?'descending':'ascending');});
doc.addEventListener('input',e=>{const f=e.target.closest('[data-table-filter]');const root=f&&f.closest('[data-behavior=\"table\"]');if(root)tblFilter(root);});
const initTable=root=>{if(root.__jpTable)return;root.__jpTable=true;const {count}=tblParts(root);if(count)tblFilter(root);};

/* ---- init / hydrate */
const hydrate=(root)=>{root=root||doc;root.querySelectorAll('[data-behavior=\"tabs\"]').forEach(initTabs);root.querySelectorAll('[data-behavior=\"radiogroup\"]').forEach(initRadiogroup);root.querySelectorAll('[data-behavior=\"toast\"] .dds-ext-toast').forEach(armToast);root.querySelectorAll('[data-behavior=\"tooltip\"]').forEach(armTooltip);root.querySelectorAll('[data-behavior=\"slider\"]').forEach(initSlider);root.querySelectorAll('[data-behavior=\"table\"]').forEach(initTable);if(root!==doc&&root.matches){if(root.matches('[data-behavior=\"tabs\"]'))initTabs(root);if(root.matches('[data-behavior=\"radiogroup\"]'))initRadiogroup(root);if(root.matches('[data-behavior=\"tooltip\"]'))armTooltip(root);if(root.matches('[data-behavior=\"slider\"]'))initSlider(root);if(root.matches('[data-behavior=\"table\"]'))initTable(root);}return root;};
const api=Object.freeze({hydrate,toast,openDialog,closeDialog,openMenu,closeMenu,selectTab,openPopover,closePopover,place,version:'0.2.0'});
globalThis.jpGoDds=Object.assign(globalThis.jpGoDds||{},{behavior:api});
if(doc.readyState==='loading')doc.addEventListener('DOMContentLoaded',()=>hydrate());else hydrate();
})();
")

(def css
  "The layer rules the markers need — see the namespace docstring. Emit
   after tokens/bridge-css (the values are --hig-* with DADS fallbacks)."
  "[data-behavior] [hidden]{display:none!important}
[data-behavior=menu]{position:relative}
[data-menu-popup][data-chrome=float]{position:absolute;inset-inline-end:0;top:calc(100% + var(--hig-spacing-1,calc(4 / 16 * 1rem)));z-index:var(--hig-z-float,40);min-inline-size:13rem;max-inline-size:min(24rem,calc(100vw - 2rem));box-sizing:border-box}
[data-behavior=menu][data-menu-align=start] [data-menu-popup][data-chrome=float]{inset-inline-end:auto;inset-inline-start:0}
[data-behavior=menu][data-menu-placement=up] [data-menu-popup][data-chrome=float]{top:auto;inset-block-end:calc(100% + var(--hig-spacing-1,calc(4 / 16 * 1rem)))}
[data-behavior=combobox],[data-behavior=select]{position:relative}
[data-behavior=combobox] [role=listbox][data-chrome=float],[data-behavior=select] [role=listbox][data-chrome=float]{position:absolute;inset-inline:0;top:calc(100% + var(--hig-spacing-1,calc(4 / 16 * 1rem)));z-index:var(--hig-z-float,40);max-block-size:min(20rem,60dvh);overflow:auto;overscroll-behavior:contain;box-sizing:border-box;margin:0;padding:var(--hig-spacing-2,calc(8 / 16 * 1rem));list-style:none;background:var(--hig-color-system-background,var(--color-neutral-white));color:var(--hig-color-label,var(--color-neutral-solid-gray-800));border:1px solid var(--hig-color-separator,var(--color-neutral-solid-gray-300));border-radius:var(--hig-radius-sm,calc(8 / 16 * 1rem));box-shadow:0 8px 24px rgb(0 0 0 / 16%)}
[data-behavior=combobox] [role=option],[data-behavior=select] [role=option]{cursor:pointer}
[data-behavior=combobox] [role=option][aria-selected=true],[data-behavior=select] [role=option][aria-selected=true]{outline:2px solid var(--hig-color-tint,var(--color-key-900));outline-offset:-2px}
[data-behavior=select] [role=combobox]{inline-size:100%;justify-content:space-between}
[data-chrome=float][data-placement=up]{top:auto;inset-block-end:calc(100% + var(--hig-spacing-1,calc(4 / 16 * 1rem)))}
[data-behavior=popover]{position:relative;display:inline-block}
[data-popover-panel][data-chrome=float]{position:absolute;inset-inline-start:0;top:calc(100% + var(--hig-spacing-1,calc(4 / 16 * 1rem)));z-index:var(--hig-z-float,40);min-inline-size:14rem;max-inline-size:min(24rem,calc(100vw - 2rem));box-sizing:border-box;padding:var(--hig-spacing-4,1rem);border-radius:var(--hig-radius-sm,calc(8 / 16 * 1rem));background:var(--hig-color-system-background,var(--color-neutral-white));border:1px solid var(--hig-color-separator,var(--color-neutral-solid-gray-420));box-shadow:0 8px 24px rgb(0 0 0 / 12%)}
[data-behavior=popover][data-popover-align=end] [data-popover-panel][data-chrome=float]{inset-inline-start:auto;inset-inline-end:0}
[data-behavior=tooltip]{position:relative;display:inline-block}
[data-behavior=tooltip] [role=tooltip]{position:absolute;inset-inline-start:50%;translate:-50% 0;inset-block-end:calc(100% + var(--hig-spacing-1,calc(4 / 16 * 1rem)));z-index:var(--hig-z-toast,80);box-sizing:border-box;padding:var(--hig-spacing-1,calc(4 / 16 * 1rem)) var(--hig-spacing-2,calc(8 / 16 * 1rem));border-radius:var(--hig-radius-xs,calc(6 / 16 * 1rem));background:var(--hig-color-label,var(--color-neutral-solid-gray-900));color:var(--hig-color-system-background,var(--color-neutral-white));font-size:var(--hig-text-caption1-font-size,calc(12 / 16 * 1rem));line-height:var(--hig-text-caption1-line-height,calc(16 / 16 * 1rem));white-space:nowrap;max-inline-size:min(20rem,calc(100vw - 2rem));pointer-events:none}
[data-behavior=tooltip] [role=tooltip][data-placement=down]{inset-block-end:auto;top:calc(100% + var(--hig-spacing-1,calc(4 / 16 * 1rem)))}
[data-behavior=slider]{--slider-value:0%;position:relative;display:block;inline-size:100%;padding-block:var(--hig-spacing-3,calc(12 / 16 * 1rem));touch-action:none}
[data-slider-track]{position:relative;block-size:.25rem;border-radius:9999px;background:var(--hig-color-separator,var(--color-neutral-solid-gray-420))}
[data-slider-track]::before{content:'';position:absolute;inset-block:0;inset-inline-start:0;inline-size:var(--slider-value);border-radius:inherit;background:var(--hig-color-tint,var(--color-key-900))}
[data-behavior=slider] [role=slider]{position:absolute;top:50%;inset-inline-start:var(--slider-value);translate:-50% -50%;inline-size:1.5rem;block-size:1.5rem;border-radius:50%;box-sizing:border-box;background:var(--hig-color-system-background,var(--color-neutral-white));border:2px solid var(--hig-color-tint,var(--color-key-900));cursor:grab}
[data-behavior=slider] [role=slider]:focus-visible{outline:2px solid var(--hig-color-tint,var(--color-key-900));outline-offset:2px}
[data-behavior=table] th[aria-sort] button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer;display:inline-flex;align-items:center;gap:var(--hig-spacing-1,calc(4 / 16 * 1rem));min-block-size:2.75rem}
[data-behavior=table] th[aria-sort] button::after{content:'';inline-size:.5em;block-size:.5em;border-inline-end:2px solid currentcolor;border-block-end:2px solid currentcolor;opacity:.35;rotate:45deg;translate:0 -.15em}
[data-behavior=table] th[aria-sort=ascending] button::after{opacity:1;rotate:-135deg;translate:0 .15em}
[data-behavior=table] th[aria-sort=descending] button::after{opacity:1}
[data-behavior=table] th[aria-sort] button:focus-visible{outline:2px solid var(--hig-color-tint,var(--color-key-900));outline-offset:2px}
[data-behavior=table] [data-table-toolbar]{display:flex;align-items:center;gap:var(--hig-spacing-3,calc(12 / 16 * 1rem));margin-block-end:var(--hig-spacing-3,calc(12 / 16 * 1rem))}
[data-behavior=table] [data-table-count]{margin-inline-start:auto;color:var(--hig-color-secondary-label,var(--color-neutral-solid-gray-600));font-size:var(--hig-text-footnote-font-size,calc(13 / 16 * 1rem))}
dialog[data-behavior=dialog]{z-index:var(--hig-z-modal,60)}
[data-behavior=toast]{position:fixed;inset-inline:0;inset-block-end:calc(var(--hig-spacing-4,1rem) + env(safe-area-inset-bottom,0px));z-index:var(--hig-z-toast,80);display:grid;justify-items:center;gap:var(--hig-spacing-2,calc(8 / 16 * 1rem));margin:0;padding:0 var(--hig-spacing-4,1rem);pointer-events:none}
.dds-ext-toast{pointer-events:auto;display:flex;align-items:center;gap:var(--hig-spacing-3,calc(12 / 16 * 1rem));max-inline-size:min(36rem,100%);min-block-size:2.75rem;padding:var(--hig-spacing-2,calc(8 / 16 * 1rem)) var(--hig-spacing-2,calc(8 / 16 * 1rem)) var(--hig-spacing-2,calc(8 / 16 * 1rem)) var(--hig-spacing-4,1rem);border-radius:var(--hig-radius-sm,calc(8 / 16 * 1rem));background:var(--hig-color-label,var(--color-neutral-solid-gray-800));color:var(--hig-color-system-background,var(--color-neutral-white));box-shadow:0 8px 24px rgb(0 0 0 / 24%);opacity:1;transition:opacity var(--hig-motion-reveal,180ms) ease-out,translate var(--hig-motion-reveal,180ms) ease-out}
.dds-ext-toast[data-leaving]{opacity:0;translate:0 var(--hig-spacing-2,calc(8 / 16 * 1rem))}
.dds-ext-toast__text{margin:0;font-size:var(--hig-text-subheadline-font-size,calc(15 / 16 * 1rem));line-height:var(--hig-text-subheadline-line-height,calc(20 / 16 * 1rem))}
.dds-ext-toast__action,.dds-ext-toast__close{font:inherit;color:inherit;background:none;border:0;min-block-size:2.75rem;min-inline-size:2.75rem;padding:0 var(--hig-spacing-2,calc(8 / 16 * 1rem));border-radius:var(--hig-radius-xs,calc(6 / 16 * 1rem));cursor:pointer}
.dds-ext-toast__action{font-weight:700;text-decoration:underline;text-underline-offset:.2em}
.dds-ext-toast__action:hover,.dds-ext-toast__close:hover{background:rgb(255 255 255 / 12%)}
.dds-ext-toast__action:focus-visible,.dds-ext-toast__close:focus-visible{outline:2px solid var(--hig-color-system-background,var(--color-neutral-white));outline-offset:2px}
.dds-ext-toast[data-tone=error]{background:var(--hig-palette-red,var(--color-primitive-red-800))}
.dds-ext-toast[data-tone=success]{background:var(--hig-palette-green,var(--color-primitive-green-700))}
@media(prefers-reduced-motion:reduce){.dds-ext-toast{transition:none}}
@media(max-width:480px){[data-menu-popup][data-chrome=float]{inset-inline:0;max-inline-size:none}}
")

(defn dialog-open-attrs
  "Attributes for the control that opens dialog `id` — the HTML invoker
   pair (command / commandfor; native where the browser has it, answered
   by `script` where it does not). `(button \"開く\" {:attrs (dialog-open-attrs \"d\")})`."
  [id]
  {:command "show-modal" :commandfor id})

(defn dialog-close-attrs
  "Attributes for a control inside dialog `id` that closes it."
  [id]
  {:command "close" :commandfor id})

(def language-selector-script
  "(()=>{'use strict';\nif(window.__ddsLanguageSelector)return;window.__ddsLanguageSelector=true;\nconst roots=()=>[...document.querySelectorAll('[data-language-selector]')];\nconst parts=root=>({opener:root.querySelector('[data-language-selector-opener]'),popup:root.querySelector('[data-language-selector-popup]'),search:root.querySelector('[data-language-selector-search]'),items:[...root.querySelectorAll('[data-language-selector-item]')]});\nconst normalize=s=>s.normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'').toLocaleLowerCase().trim();\nconst filter=root=>{const {search,items}=parts(root);const term=normalize(search?.value||'');let count=0;items.forEach(item=>{const show=normalize(item.dataset.languageSelectorKeywords||item.textContent).includes(term);item.parentElement.hidden=!show;if(show)count++;});const empty=root.querySelector('[data-language-selector-empty]');if(empty)empty.hidden=count>0;};\nconst close=root=>{const {opener,popup}=parts(root);if(!opener||!popup)return;popup.hidden=true;opener.setAttribute('aria-expanded','false');};\nconst open=root=>{const {opener,popup,search,items}=parts(root);if(!opener||!popup)return;roots().forEach(other=>{if(other!==root)close(other);});if(search)search.value='';filter(root);popup.hidden=false;popup.style.transform='';const rect=popup.getBoundingClientRect();const dx=rect.left<16?16-rect.left:rect.right>innerWidth-16?innerWidth-16-rect.right:0;popup.style.transform='translateX('+dx+'px)';opener.setAttribute('aria-expanded','true');(search||items.find(item=>item.hasAttribute('aria-current'))||items[0])?.focus();};\ndocument.addEventListener('input',event=>{if(event.target.matches('[data-language-selector-search]'))filter(event.target.closest('[data-language-selector]'));});\ndocument.addEventListener('click',event=>{const opener=event.target.closest('[data-language-selector-opener]');if(opener){const root=opener.closest('[data-language-selector]');opener.getAttribute('aria-expanded')==='true'?close(root):open(root);return;}roots().forEach(root=>{if(!root.contains(event.target)||event.target.closest('[data-language-selector-item]'))close(root);});});\ndocument.addEventListener('focusin',event=>roots().forEach(root=>{if(!root.contains(event.target))close(root);}));\ndocument.addEventListener('keydown',event=>{const root=event.target.closest('[data-language-selector]');if(!root)return;const {opener,popup,search,items:all}=parts(root);if(event.key==='Escape'){event.preventDefault();close(root);opener?.focus();return;}if(popup?.hidden)return;const items=all.filter(item=>!item.parentElement.hidden);if(!items.length)return;const current=items.indexOf(document.activeElement);let next=null;if(event.key==='ArrowDown')next=(current+1)%items.length;if(event.key==='ArrowUp')next=current<0?items.length-1:(current-1+items.length)%items.length;if(document.activeElement!==search){if(event.key==='Home')next=0;if(event.key==='End')next=items.length-1;}if(next!==null){event.preventDefault();items[next].focus();}if(event.key==='Enter'&&document.activeElement===search){event.preventDefault();items[0].click();}});\n})();\n")

(def language-selector-css
  "[data-language-selector]{position:relative;flex-shrink:0;inline-size:fit-content;}\n[data-language-selector] [data-language-selector-opener]{min-block-size:2.75rem;display:flex;align-items:center;gap:.375rem;white-space:nowrap;}\n[data-language-selector-popup]{box-sizing:border-box;position:absolute;inset-inline-end:0;inset-block-start:calc(100% + .5rem);z-index:100;inline-size:min(20rem,calc(100vw - 2rem));max-block-size:min(26rem,70dvh);overflow:auto;overscroll-behavior:contain;padding:.75rem;background:var(--color-neutral-white);color:var(--color-neutral-solid-gray-900);border:1px solid var(--color-neutral-solid-gray-300);border-radius:.5rem;box-shadow:0 .5rem 1.5rem rgb(0 0 0 / .15);}\n[data-language-selector] [hidden]{display:none!important;}\n[data-language-selector-search]{box-sizing:border-box;inline-size:100%;min-block-size:2.75rem;font-size:1rem;margin-block-end:.5rem;}\n[data-language-selector-menu]{margin:0;padding:0;list-style:none;}\n[data-language-selector-item]{display:flex;align-items:center;min-block-size:2.75rem;gap:.5rem;}\n[data-language-selector-current]{max-inline-size:9rem;overflow:hidden;text-overflow:ellipsis;}\n[data-language-selector-empty]{padding:.75rem;margin:0;}\n")
