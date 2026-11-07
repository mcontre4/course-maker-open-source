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

text(c,'Move, open, verify',640,90,44);
const moved=e(t,3,4), opened=e(t,8,3), docX=300+480*moved;
rect(c,690,300,330,210,'#ca8c33');rect(c,710,270,130,55,C.gold,12);
rect(c,docX-60,235,120,165,C.ink,10);
for(let i=0;i<4;i++)line(c,docX-37,280+i*24,docX+35,280+i*24,'#60759a',5);
c.save();c.translate(690,340+70*opened);c.transform(1,0,-.2*opened,1,0,0);rect(c,0,0,330,170-50*opened,C.gold,16);c.restore();
text(c,moved<1?'Move the document':'Open the destination',640,590,34,C.cyan);
if(t>=12){line(c,1040,320,1070,350,C.cyan,8);line(c,1070,350,1125,280,C.cyan,8);text(c,'Verify the document is inside',640,650,34,C.cyan);}

c.restore();};
window.visualPlan=[{"scene_id": "reference", "at_sec": 2, "composition": "Establish the document and folder; move the document.", "objects": ["document"]}, {"scene_id": "reference", "at_sec": 9, "composition": "Open the folder while retaining document identity.", "objects": ["folder"]}, {"scene_id": "reference", "at_sec": 15, "composition": "Add a small check beside the actual document.", "objects": ["document inside folder"]}];
window.cueEvents=[];
})();
