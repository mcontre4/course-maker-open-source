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

text(c,'Compare at the same scale',640,90,44);
const levelA=350, levelB=350-120*e(t,5,4);
for(const [x,y,name,col] of [[300,levelA,'A',C.cyan],[800,levelB,'B',C.pink]]){
 rect(c,x,200,180,300,'#253b60');rect(c,x+12,y,156,488-y,col,6);
 line(c,x,200,x,500,C.ink,5);line(c,x+180,200,x+180,500,C.ink,5);line(c,x,500,x+180,500,C.ink,5);
 text(c,name,x+90,564,40,col);
}
line(c,180,500,1100,500,C.muted,2);
if(t>=10){line(c,1060,levelB,1060,levelA,C.gold,5);line(c,1038,levelB,1082,levelB,C.gold,4);line(c,1038,levelA,1082,levelA,C.gold,4);text(c,'Difference',1020,620,34,C.gold);}

c.restore();};
window.visualPlan=[{"scene_id": "reference", "at_sec": 2, "composition": "Establish both containers and matching levels.", "objects": ["containers"]}, {"scene_id": "reference", "at_sec": 7, "composition": "Raise the right liquid; keep framing locked.", "objects": ["second liquid level"]}, {"scene_id": "reference", "at_sec": 13, "composition": "Add a bracket beside the changed level.", "objects": ["gap between levels"]}];
window.cueEvents=[];
})();
