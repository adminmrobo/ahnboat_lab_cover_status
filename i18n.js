/* 홈페이지 다국어 도우미 — top·catalog·schedule 페이지가 함께 쓴다.
   - 언어: ?lang= → 이 사이트에 기억된 언어(localStorage 'ahnboat-lang') → 한국어
   - 사전: data/i18n/site.json  {"str": {한국어 원문: {en,zh,ja,uz,ru,vi}}}  — 없는 말은 한국어 그대로
   - 바꾸면: 같은 사이트의 다른 블록은 storage 이벤트로, 워드프레스 쪽 블록은 부모 창에 보내는 메시지로 함께 바뀐다.
   사용: AhnI18n.ready.then(fn) · AhnI18n.t('{0}개 콘텐츠', 12) · AhnI18n.onChange(fn) · AhnI18n.set('en') */
(function(){
  'use strict';
  var KEY='ahnboat-lang',LANGS=['ko','en','zh','ja','uz','ru','vi'];
  var NAMES={ko:'한국어',en:'English',zh:'中文',ja:'日本語',uz:'Oʻzbekcha',ru:'Русский',vi:'Tiếng Việt'};
  var base=(document.currentScript&&document.currentScript.src||'').replace(/i18n\.js(\?.*)?$/,'');
  function ok(l){return LANGS.indexOf(l)>=0;}
  function stored(){try{return localStorage.getItem(KEY)||'';}catch(e){return '';}}
  function store(l){try{localStorage.setItem(KEY,l);}catch(e){}}
  var q=new URLSearchParams(location.search).get('lang');
  var lang=ok(q)?q:(ok(stored())?stored():'ko');
  if(ok(q))store(q);
  var DICT=null,LINKS=null,loading=null,subs=[];
  function load(){
    if(DICT)return Promise.resolve();
    if(!loading)loading=Promise.all([
      fetch(base+'data/i18n/site.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():{str:{}};}).catch(function(){return {str:{}};}),
      fetch(base+'data/i18n/links.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():{};}).catch(function(){return {};})
    ]).then(function(a){DICT=a[0].str||{};LINKS=a[1]||{};});
    return loading;
  }
  function apply(){document.documentElement.lang=lang==='zh'?'zh-CN':lang;}
  function fill(s,args){return String(s).replace(/\{(\d+)\}/g,function(m,n){return args[+n]!=null?args[+n]:m;});}
  function t(ko){var args=[].slice.call(arguments,1);if(ko==null)return ko;var s=String(ko);
    if(lang!=='ko'&&DICT){var e=DICT[s.trim()];if(e&&e[lang])s=e[lang];}return fill(s,args);}
  /* 숫자를 굵게: '{0}개 콘텐츠' → [텍스트, <b>12</b>, 텍스트] 를 부모에 붙인다 */
  function nb(parent,ko,n){var s=t(ko),i=s.indexOf(String(n));
    var parts=t(ko,'\u0000').split('\u0000');
    if(parts.length<2){parent.appendChild(document.createTextNode(fill(s,[n])));return;}
    if(parts[0])parent.appendChild(document.createTextNode(parts[0]));var b=document.createElement('b');b.textContent=String(n);parent.appendChild(b);
    if(parts[1])parent.appendChild(document.createTextNode(parts[1]));}
  /* 콘텐츠의 이 언어판 주소(없으면 원래 주소와 false) */
  function link(repoUrl,siteUrl){
    if(lang==='ko'||!LINKS||!repoUrl)return [siteUrl,lang==='ko'];
    var m=(repoUrl.match(/github\.com\/[^\/]+\/([^\/?#]+)/)||[])[1];var u=m&&LINKS[m]&&LINKS[m][lang];
    return u?[u,true]:[siteUrl,false];}
  function emit(){subs.forEach(function(f){try{f(lang);}catch(e){}});}
  function tellParent(){if(window.parent!==window){try{window.parent.postMessage({type:'ahnboat-lang',lang:lang},'*');}catch(e){}}}
  function change(l,fromOutside){
    if(!ok(l)||l===lang)return Promise.resolve();
    lang=l;apply();if(!fromOutside){store(l);tellParent();}
    return load().then(emit);
  }
  window.addEventListener('storage',function(e){if(e.key===KEY&&ok(e.newValue))change(e.newValue,true);});
  window.addEventListener('message',function(e){var d=e.data;if(d&&d.type==='ahnboat-lang-set'&&ok(d.lang)){store(d.lang);change(d.lang,true);}});
  apply();
  var ready=(lang==='ko'?Promise.resolve():load()).then(function(){});
  window.AhnI18n={
    get lang(){return lang;},langs:LANGS,names:NAMES,ready:ready,t:t,nb:nb,link:link,
    set:function(l){return change(l,false);},
    onChange:function(f){subs.push(f);},
    announce:tellParent,
    load:load
  };
})();
