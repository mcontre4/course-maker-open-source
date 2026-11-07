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

text(c,t<6?'2x + 3 = 11':t<12?'2x = 8':'x = 4',640,100,64,C.gold);
line(c,640,170,640,560,C.muted,2);
const removed=e(t,4,2), opened=e(t,11,3);
for(let bag=0;bag<2;bag++){
 const x=235+bag*190;
 c.globalAlpha=1-opened;rect(c,x-60,265,120,155,'#466491');text(c,'x',x,360,58);c.globalAlpha=1;
 if(opened>0){c.globalAlpha=opened;for(let i=0;i<4;i++)disc(c,x-25+(i%2)*50,300+Math.floor(i/2)*54,17,C.cyan);c.globalAlpha=1;}
}
for(let i=0;i<3;i++)disc(c,250+i*70,480+100*removed,17,C.pink);
for(let i=0;i<11;i++){
 const removedDot=i<3, k=removedDot?i:i-3;
 const x=removedDot?800+i*70:780+(k%4)*65;
 const y=removedDot?245+335*removed:345+Math.floor(k/4)*65;
 disc(c,x,y,17,removedDot?C.pink:C.cyan);
}
if(t>=6&&t<12)text(c,'Remove three from both sides',640,652,34,C.pink);
if(t>=12)text(c,'Four in each equal group',640,652,32,C.cyan);

c.restore();};
window.visualPlan=[{"scene_id": "reference", "at_sec": 2, "composition": "Establish the balanced quantities and equation.", "objects": ["two pouches and beads"]}, {"scene_id": "reference", "at_sec": 8, "composition": "Move the pink beads to the same lower tray on each side.", "objects": ["three beads on each side"]}, {"scene_id": "reference", "at_sec": 15, "composition": "Open the pouches to reveal four beads each.", "objects": ["equal groups"]}];
window.cueEvents=[];
})();
