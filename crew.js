/* 연구실 식구 동작 (fruitfly-lab-expressions 동작 라이브러리 v1.1 프레임 사용)
   - 키 비율: 박사 1.0, 하루 0.9, 주판봇 0.7, 초파리 0.4 (data/motion.json 의 scale 로 맞춤)
   - 프레임마다 발 기준선(ground_y)을 같은 선에 세운다.
   사용: AhnCrew.load().then(function(){ AhnCrew.make('doctor', 박사키px) }) → {el, act(), talk} */
(function(){
  'use strict';
  var M=null,reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  var PLAN={
    doctor:{idle:['D1','idle'],acts:[['D4','win'],['D2','jump'],['D1','walk']]},
    haru:{idle:['A1','idle'],acts:[['A4','win'],['A2','jump'],['A1','walk']]},
    jupanbot:{idle:['R1','idle'],acts:[['R1','count'],['R2','cheer']]},
    fruitfly:{idle:['F1','idle'],acts:[['F1','start'],['F3','suspect'],['F2','point_left']]}
  };
  function frames(sid,seg){var s=M.sheets[sid],r=s.seg[seg]||[1,s.frames.length],o=[];for(var i=r[0];i<=r[1];i++)o.push([sid,i-1]);return o;}
  function make(who,H){
    var p=PLAN[who];var box=document.createElement('span');box.className='crewsprite '+who;
    box.style.cssText='position:relative;display:inline-block;vertical-align:bottom;';
    var img=document.createElement('img');img.alt='';img.decoding='async';
    img.style.cssText='position:absolute;left:50%;transform:translateX(-50%);image-rendering:pixelated;pointer-events:none;';
    box.appendChild(img);
    // 상자 크기: 기본 대기 시트 기준
    var base=M.sheets[p.idle[0]];
    box.style.width=Math.round(base.frame_size[0]*base.scale*H)+'px';
    box.style.height=Math.round(base.ground_y*base.scale*H)+'px';
    var queue=[],idle=frames(p.idle[0],p.idle[1]),k=0;
    function show(f){var s=M.sheets[f[0]];img.src=s.frames[f[1]];
      img.style.height=(s.frame_size[1]*s.scale*H)+'px';img.style.width=(s.frame_size[0]*s.scale*H)+'px';
      img.style.bottom=(-(s.frame_size[1]-s.ground_y)*s.scale*H)+'px';}
    function tick(){var f;if(queue.length)f=queue.shift();else{f=idle[k%idle.length];k++;}show(f);}
    show(idle[0]);
    var timer=reduce?null:setInterval(tick,150);
    function act(i){var a=p.acts[(i==null?Math.floor(Math.random()*p.acts.length):i)%p.acts.length];var fr=frames(a[0],a[1]);queue=fr.concat(fr.length<=4?fr:[]);if(reduce)show(fr[fr.length-1]);}
    return {el:box,act:act,who:who};
  }
  function preload(){Object.keys(M.sheets).forEach(function(k){M.sheets[k].frames.forEach(function(s){var i=new Image();i.src=s;});});}
  window.AhnCrew={
    load:function(){return fetch('data/motion.json',{cache:'no-cache'}).then(function(r){return r.json();}).then(function(d){M=d;preload();return d;});},
    make:make
  };
})();
