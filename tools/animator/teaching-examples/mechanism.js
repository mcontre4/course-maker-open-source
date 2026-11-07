(function(){
"use strict";
const C={bg:'#111538',ink:'#fff9ed',muted:'#bbc7e8',gold:'#ffd05b',cyan:'#66e6ed',pink:'#fa82aa'};
const p=(t,a,d=2)=>Math.max(0,Math.min(1,(t-a)/d));
const e=(t,a,d=2)=>{const v=p(t,a,d);return v*v*(3-2*v);};
function text(c,s,x,y,z=32,col=C.ink){c.fillStyle=col;c.font=`600 ${z}px sans-serif`;c.textAlign='center';c.fillText(s,x,y);}
function line(c,x,y,X,Y,col=C.gold,w=5){c.strokeStyle=col;c.lineWidth=w;c.lineCap='round';c.beginPath();c.moveTo(x,y);c.lineTo(X,Y);c.stroke();}
function disc(c,x,y,r,col){const g=c.createRadialGradient(x-r*.3,y-r*.4,0,x,y,r);g.addColorStop(0,col);g.addColorStop(1,col+'99');c.fillStyle=g;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill();}
function rect(c,x,y,w,h,col,r=16){c.fillStyle=col;c.beginPath();c.roundRect(x,y,w,h,r);c.fill();}
window.scoreSound=function(){};
window.explainer=function(c,W,H,t){c.save();c.scale(W/1280,H/720);c.fillStyle=C.bg;c.fillRect(0,0,1280,720);

const sunY=50+130*e(t,6,5), end=480+220*200/(300-sunY);
text(c,'Light angle changes the shadow',640,90,44);
rect(c,100,500,1080,12,'#526d92',6);
line(c,480,500,end,500,'#111122',22);
rect(c,468,300,24,200,C.cyan,7);
disc(c,260,sunY,34,C.gold);
const trace=e(t,2,3);line(c,260,sunY,260+(end-260)*trace,sunY+(500-sunY)*trace,C.gold,4);
text(c,'Same object height',480,558,30);
if(t>=6)text(c,'Lower light',260,255,30,C.gold);
if(t>=12){line(c,480,610,end,610,C.pink,4);text(c,'Longer shadow', (480+end)/2,661,36,C.pink);}

c.restore();};
window.visualPlan=[{"scene_id": "reference", "at_sec": 3, "composition": "Trace the ray to its ground intersection.", "objects": ["light ray"]}, {"scene_id": "reference", "at_sec": 9, "composition": "Lower the light and extend the same ray and shadow.", "objects": ["ray endpoint"]}, {"scene_id": "reference", "at_sec": 15, "composition": "Settle and add a short result label.", "objects": ["shadow length"]}];
window.cueEvents=[];
})();
