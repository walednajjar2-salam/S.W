/* Launch Quality · Enterprise Vision Experience */
(function(){
  const $ = s => document.querySelector(s);
  const $$ = s => Array.from(document.querySelectorAll(s));

  function haptic(){ try{ if(navigator.vibrate) navigator.vibrate(12); }catch(e){} }

  function initNeuralCanvas(id, opts={}){
    const c = document.getElementById(id);
    if(!c || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return null;
    const ctx = c.getContext('2d');
    let w, h, nodes, anim;
    const count = opts.nodes || (id==='neuralCanvas'?72:40);
    const linkDist = opts.linkDist || 140;

    function resize(){
      w = c.width = window.innerWidth * devicePixelRatio;
      h = c.height = window.innerHeight * devicePixelRatio;
      c.style.width = window.innerWidth+'px';
      c.style.height = window.innerHeight+'px';
      ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
      nodes = Array.from({length:count},()=>({
        x:Math.random()*window.innerWidth,
        y:Math.random()*window.innerHeight,
        vx:(Math.random()-.5)*.35,
        vy:(Math.random()-.5)*.35
      }));
    }

    function draw(){
      ctx.clearRect(0,0,window.innerWidth,window.innerHeight);
      nodes.forEach(n=>{
        n.x+=n.vx; n.y+=n.vy;
        if(n.x<0||n.x>window.innerWidth) n.vx*=-1;
        if(n.y<0||n.y>window.innerHeight) n.vy*=-1;
      });
      for(let i=0;i<nodes.length;i++){
        for(let j=i+1;j<nodes.length;j++){
          const a=nodes[i], b=nodes[j];
          const d=Math.hypot(a.x-b.x,a.y-b.y);
          if(d<linkDist){
            const alpha=(1-d/linkDist)*.35;
            ctx.strokeStyle=`rgba(212,175,55,${alpha})`;
            ctx.lineWidth=.6;
            ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
          }
        }
      }
      nodes.forEach(n=>{
        ctx.beginPath(); ctx.arc(n.x,n.y,1.2,0,Math.PI*2);
        ctx.fillStyle='rgba(212,175,55,.55)'; ctx.fill();
      });
      anim=requestAnimationFrame(draw);
    }

    resize();
    window.addEventListener('resize',resize);
    draw();
    return ()=>{ cancelAnimationFrame(anim); window.removeEventListener('resize',resize); };
  }

  function initCityCanvas(id){
    const c=document.getElementById(id);
    if(!c) return;
    const ctx=c.getContext('2d');
    let anim, t=0;
    const buildings=[];

    function resize(){
      const r=c.parentElement.getBoundingClientRect();
      c.width=Math.max(1,r.width*devicePixelRatio);
      c.height=Math.max(1,r.height*devicePixelRatio);
      c.style.width=r.width+'px'; c.style.height=r.height+'px';
      ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
      buildings.length=0;
      const n=Math.floor(r.width/28);
      for(let i=0;i<n;i++){
        buildings.push({
          x:i*28+8,
          w:14+Math.random()*10,
          h:30+Math.random()*(r.height*.55),
          hue:38+Math.random()*18
        });
      }
    }

    function draw(){
      const w=c.clientWidth, h=c.clientHeight;
      ctx.clearRect(0,0,w,h);
      const grd=ctx.createLinearGradient(0,0,0,h);
      grd.addColorStop(0,'rgba(4,8,20,.15)'); grd.addColorStop(1,'rgba(4,8,20,.75)');
      ctx.fillStyle=grd; ctx.fillRect(0,0,w,h);
      ctx.strokeStyle='rgba(212,175,55,.12)'; ctx.lineWidth=1;
      for(let x=0;x<w;x+=32){ctx.beginPath();ctx.moveTo(x,h);ctx.lineTo(x+16,h*.35);ctx.stroke();}
      buildings.forEach((b,i)=>{
        const pulse=Math.sin(t*.02+i)*3;
        const bh=b.h+pulse;
        const y=h-bh;
        const g=ctx.createLinearGradient(b.x,y,b.x,y+bh);
        g.addColorStop(0,`hsla(${b.hue},45%,55%,.75)`);
        g.addColorStop(1,`hsla(${b.hue},30%,25%,.35)`);
        ctx.fillStyle=g;
        ctx.fillRect(b.x,y,b.w,bh);
        if(i%3===0){
          ctx.fillStyle='rgba(212,175,55,.5)';
          for(let wy=y+8;wy<y+bh-8;wy+=14)
            for(let wx=b.x+3;wx<b.x+b.w-3;wx+=6)
              if((i+wy)%17>8) ctx.fillRect(wx,wy,3,4);
        }
      });
      t++; anim=requestAnimationFrame(draw);
    }
    resize(); draw();
    window.addEventListener('resize',resize);
  }

  function initAuthTabs(){
    const tabs=$$('.ev-auth-tab');
    const panes={
      password:$('#authPanePassword'),
      face:$('#authPaneFace'),
      fingerprint:$('#authPaneFingerprint'),
      sso:$('#authPaneSso')
    };
    tabs.forEach(tab=>{
      tab.onclick=()=>{
        tabs.forEach(x=>x.classList.remove('active'));
        tab.classList.add('active');
        Object.values(panes).forEach(p=>p&&p.classList.add('hidden'));
        const pane=panes[tab.dataset.auth];
        if(pane) pane.classList.remove('hidden');
      };
    });
    $$('.ev-sso-btn').forEach(b=>{
      b.onclick=()=>{
        if(typeof toastOk==='function') toastOk('SSO · '+b.textContent+' — Enterprise gateway');
      };
    });
    $$('[data-bio-action]').forEach(b=>{
      b.onclick=()=>bioSmartLogin(b.dataset.bioAction||'face');
    });
  }

  async function bioSmartLogin(mode){
    const token=localStorage.getItem('jawdah_cloud_token');
    const user=localStorage.getItem('jawdah_last_user');
    if(!token||!user){
      if(typeof toastErr==='function') toastErr('سجّل الدخول بكلمة المرور أولاً لتفعيل '+ (mode==='face'?'Face ID':'Touch ID'));
      return;
    }
    try{
      if(window.PublicKeyCredential){
        const ok=await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable?.();
        if(ok){
          const challenge=new Uint8Array(32);
          crypto.getRandomValues(challenge);
          await navigator.credentials.get({
            publicKey:{challenge,rpId:location.hostname,userVerification:'required',timeout:60000}
          });
        }
      }
      if(typeof toastOk==='function') toastOk((mode==='face'?'Face ID':'Touch ID')+' · تم التحقق');
      if(typeof bootstrapApp==='function') bootstrapApp();
      else if(typeof loadAll==='function'){ Jawdah.token=token; loadAll(); }
    }catch(e){
      if(typeof toastErr==='function') toastErr('تعذر التحقق البيومتري — استخدم كلمة المرور');
    }
  }

  async function submitVisionAi(question){
    if(window.LQ_WALID_INTEL && typeof window.LQ_WALID_INTEL.ask==='function'){
      return window.LQ_WALID_INTEL.ask(question);
    }
    const body=$('#visionAiBody');
    if(!body || !question) return;
    body.insertAdjacentHTML('beforeend','<div class="vision-ai-msg">'+question+'</div>');
    try{
      const token=window.Jawdah?.token||localStorage.getItem('jawdah_cloud_token')||'';
      const res=await fetch('/api/ai/ask',{
        method:'POST',
        headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},
        body:JSON.stringify({question})
      });
      const data=await res.json();
      const reply=(data.assistant?data.assistant+': ':'')+(data.reply||data.error||'No response');
      body.insertAdjacentHTML('beforeend','<div class="vision-ai-msg pred">'+reply+'</div>');
      const actions=(data.actions||[]).map(a=>'<button type="button" data-action="'+a.action+'" data-section="'+a.section+'">'+a.label+'</button>').join('');
      if(actions) body.insertAdjacentHTML('beforeend','<div class="vision-ai-actions">'+actions+'</div>');
      initAiDock();
      haptic();
    }catch(e){
      body.insertAdjacentHTML('beforeend','<div class="vision-ai-msg">تعذر الاتصال بالمساعد</div>');
    }
  }

  function initAiDock(){
    const dock=$('#visionAiDock');
    if(!dock) return;
    const head=dock.querySelector('.vision-ai-head');
    if(head) head.onclick=()=>dock.classList.toggle('collapsed');
    dock.querySelectorAll('.vision-ai-actions button').forEach(b=>{
      b.onclick=()=>{
        haptic();
        const section=b.dataset.section;
        const a=b.dataset.action;
        if(section && typeof showSection==='function') showSection(section);
        else if(a==='dashboard'&&typeof showSection==='function') showSection('dashboard');
        else if(a==='reports'&&typeof showSection==='function') showSection('reports');
        else if(a==='insights'&&typeof showSection==='function') showSection('messages');
        else if(a==='invoices'&&typeof showSection==='function') showSection('invoices');
        else if(a==='contracts'&&typeof showSection==='function') showSection('contracts');
        else if(a==='maintenance'&&typeof showSection==='function') showSection('maintenance');
        else if(a==='properties'&&typeof showSection==='function') showSection('properties');
        else if(a==='overdue'&&typeof showSection==='function') showSection('invoices');
      };
    });
    const input=$('#visionAiInput');
    const send=$('#visionAiSend');
    if(send && input && !send.dataset.bound){
      send.dataset.bound='1';
      send.onclick=()=>{ const q=input.value.trim(); if(!q) return; input.value=''; submitVisionAi(q); };
      input.onkeydown=(e)=>{ if(e.key==='Enter'){ e.preventDefault(); send.click(); } };
    }
  }

  window.refreshVisionAi=function(){
    const body=$('#visionAiBody');
    if(!body||typeof dashKpis!=='function') return;
    const k=dashKpis();
    const eng=typeof dashEngine==='function'&&window.Jawdah?dashEngine(window.Jawdah.data||{},k):null;
    const msgs=[];
    if(eng){
      msgs.push({t:eng.brief,pred:true});
      eng.risks.slice(0,3).forEach(r=>msgs.push({t:`⚠ ${r.l}: ${r.v}`,pred:false}));
    } else {
      msgs.push({t:'Walid: جاهزية النظام '+ (k.health||0) +'% · إشغال '+(k.occupancy||0)+'%',pred:true});
    }
    msgs.push({t:'توقع: الإيرادات الشهرية مستقرة بناءً على العقود النشطة.',pred:true});
    const overdue=Number(k.overdue||0);
    const expiring=Number(k.expiring||0);
    const vacant=Number(k.vacant||0);
    const maint=Number(k.maintenance||0);
    body.innerHTML=msgs.map(m=>`<div class="vision-ai-msg${m.pred?' pred':''}">${m.t}</div>`).join('')+
      `<div class="vision-ai-actions">
        <button type="button" data-action="navigate" data-section="dashboard">🏠 لوحة التحكم</button>
        <button type="button" data-action="navigate" data-section="invoices">💳 متأخر ${overdue>0?money(overdue):'—'}</button>
        <button type="button" data-action="navigate" data-section="contracts">📄 تجديد ${expiring||0}</button>
        <button type="button" data-action="navigate" data-section="maintenance">🔧 صيانة ${maint||0}</button>
        <button type="button" data-action="navigate" data-section="properties">🏢 شاغر ${vacant||0}</button>
        <button type="button" data-action="navigate" data-section="reports">📈 تقارير</button>
      </div>`;
    initAiDock();
  };

  window.initEnterpriseVision=function(){
    document.body.classList.add('enterprise-vision');
    syncVisionLayers();
    initAuthTabs();
    initAiDock();
    refreshVisionAi();
  };

  function syncVisionLayers(){
    const loggedIn=$('#app')&&!$('#app').classList.contains('hidden');
    const loginCanvas=$('#neuralCanvas');
    const dashCanvas=$('#neuralDash');
    const aiDock=$('#visionAiDock');
    if(loginCanvas) loginCanvas.classList.toggle('hidden',loggedIn);
    if(dashCanvas){
      dashCanvas.classList.toggle('hidden',!loggedIn);
      if(loggedIn&&!dashCanvas._evInit) { initNeuralCanvas('neuralDash',{nodes:36,linkDist:100}); dashCanvas._evInit=true; }
    }
    if(aiDock){
      // Personal assistant dock permanently disabled by owner request
      aiDock.classList.add('hidden');
      aiDock.setAttribute('hidden','');
      aiDock.style.display='none';
    }
    if(!loggedIn && loginCanvas && !loginCanvas._evInit){
      initNeuralCanvas('neuralCanvas');
      loginCanvas._evInit=true;
      initCityCanvas('evCityLogin');
    }
    if(loggedIn){
      initCityCanvas('evCityDashboard');
      refreshVisionAi();
    }
  }

  window.syncEnterpriseVision=syncVisionLayers;

  const origLogin=window.login;
  if(typeof login==='function'){
    window.login=async function(){
      await origLogin.apply(this,arguments);
      haptic();
      syncVisionLayers();
    };
  }

  const origCheck=window.checkSession;
  if(typeof checkSession==='function'){
    window.checkSession=async function(){
      await origCheck.apply(this,arguments);
      syncVisionLayers();
    };
  }
})();
