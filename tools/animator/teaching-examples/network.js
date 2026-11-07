window.explainer = null;
const {sky,glow,spark,ball,arrow,text,pill,rr,bez,seg,back}=FV;
const TAU=Math.PI*2,cl=H.clamp,lerp=H.lerp,eo=H.ease.out,eio=H.ease.inOut;
const S2=20.48,S3=47.12;
const CT={s01:[.96,5.04,9.52,13.52,17.64],s02:[0,2.2,7.04,8.96,12.56,16.88,23.76],s03:[0,2.92,4.96,10.12,15.04]};
const c1=CT.s01,c2=CT.s02.map(v=>v+S2),c3=CT.s03.map(v=>v+S3);
const PAL={cream:['#fff0cc','#ecc088','#b4723c'],tan:['#ffe9be','#ecb676','#b4723c'],white:['#ffffff','#e1dcf7','#8d86c8'],teal:['#a4fbef','#3ccbdc','#1d64b0'],gold:['#fff1a4','#ffd15c','#bc773e'],red:['#ff9a8a','#e0445a','#8f2250'],orange:['#ffcc7a','#ff8d3f','#d24a2a'],stone:['#d9d2f2','#a79fd0','#6e66a0'],wood:['#e0a46a','#b87a45','#7a4a28']};
const SK=['#ffe0b8','#e8ae7a','#b4723c'];
const N={W1:[170,390],W2:[340,235],W3:[330,510],M1:[505,225],O:[640,360],E1:[880,285],E2:[850,510],C:[1105,365],S:[560,610]};
const ND={W1:{ty:0,s:1.25,pal:PAL.teal,nt:7.2},W2:{ty:0,s:1.15,pal:PAL.gold,nt:6.9},W3:{ty:1,s:1.2,pal:PAL.red,nt:6.6},M1:{ty:1,s:1.1,pal:PAL.orange,nt:6.2},E1:{ty:1,s:1.1,pal:PAL.teal,nt:.1},E2:{ty:1,s:1.15,pal:PAL.gold,nt:5.9},C:{ty:2,s:1.8,pal:PAL.red,nt:8.0},S:{ty:4,s:1.2,pal:PAL.orange,nt:33.2},O:{ty:3,s:1,pal:PAL.tan,nt:-1}};
const ED=[['O','E1',-16,0,.9],['O','E2',22,5.2,.9],['O','M1',-14,5.6,.8],['O','W3',14,5.9,.9],['M1','W2',-12,6.3,.8],['W2','W1',-10,6.7,.7],['W1','W3',10,7.0,.7],['E1','C',-18,7.2,1],['E2','C',16,7.5,1],['M1','E1',-48,18,1.3],['S','O',-20,33.1,1],['S','W3',-14,33.3,.9]];
const EP={};
function mk(a,b,bd){const p=N[a],q=N[b],dx=q[0]-p[0],dy=q[1]-p[1],l=Math.hypot(dx,dy),nx=-dy/l*bd,ny=dx/l*bd;return [p,[p[0]+dx/3+nx,p[1]+dy/3+ny],[p[0]+dx*2/3+nx,p[1]+dy*2/3+ny],q];}
ED.forEach(e=>EP[e[0]+e[1]]=mk(e[0],e[1],e[2]));
const gp=(a,b)=>EP[a+b]||EP[b+a].slice().reverse();
const K=[[0,3.4,770,335],[5,3.4,770,335],[8.2,1,640,360],[9.4,1,640,360],[11.6,1.3,930,350],[13.4,1.3,930,350],[16.4,1.02,640,360],[20.48,1,640,360],[22.5,2.9,640,372],[29.4,2.9,640,372],[32.6,1,640,360],[36,1,640,360],[41,1.1,760,430],[45.5,1,640,380],[47.12,1,640,360],[49,2.8,640,372],[50,2.8,640,372],[53.2,1,640,360],[64.64,1,640,360]];
function cam(t){let i=0;while(i<K.length-2&&t>=K[i+1][0])i++;const a=K[i],b=K[i+1],u=eio(seg(t,a[0],b[0]));return {z:Math.exp(lerp(Math.log(a[1]),Math.log(b[1]),u)),cx:lerp(a[2],b[2],u),cy:lerp(a[3],b[3],u)};}
function kf(t,A){if(t<=A[0][0])return A[0][1];for(let i=0;i<A.length-1;i++)if(t<A[i+1][0]){const u=eio(seg(t,A[i][0],A[i+1][0]));return [lerp(A[i][1][0],A[i+1][1][0],u),lerp(A[i][1][1],A[i+1][1][1],u)];}return A[A.length-1][1];}
function oval(x,a,b,rx,ry,col){x.fillStyle=col;x.beginPath();x.ellipse(a,b,rx,ry,0,0,TAU);x.fill();}
function shp(x,pts,col){x.fillStyle=col;x.beginPath();pts.forEach((p,i)=>i?x.lineTo(p[0],p[1]):x.moveTo(p[0],p[1]));x.closePath();x.fill();}
function box(x,a,b,w,h,col,r=6){x.fillStyle=col;rr(x,a,b,w,h,r);x.fill();}
function blk(x,X,Y,w,h,c,r=5){const g=x.createLinearGradient(X,Y,X+w,Y+h);g.addColorStop(0,c[0]);g.addColorStop(1,c[1]);x.fillStyle=g;rr(x,X,Y,w,h,r);x.fill();x.save();x.globalAlpha*=.3;x.fillStyle=c[2];rr(x,X+w*.7,Y,w*.3,h,r);x.fill();x.restore();}
function disc(x,cx,cy,rx,ry){const g=x.createLinearGradient(0,cy-ry,0,cy+ry);g.addColorStop(0,'#4b3f98');g.addColorStop(1,'#2b2468');x.fillStyle=g;x.beginPath();x.ellipse(cx,cy,rx,ry,0,0,TAU);x.fill();x.strokeStyle='rgba(190,170,255,.45)';x.lineWidth=2;x.stroke();}
function dome(x,cx,cy,r,pal){x.save();x.beginPath();x.rect(cx-r-2,cy-r-10,2*r+4,r+10);x.clip();ball(x,cx,cy,r,pal);x.restore();box(x,cx-1,cy-r-8,2,9,pal[2],1);}
function dark(x,a,b,w,h){x.fillStyle='rgba(30,22,80,.75)';rr(x,a,b,w,h,w/2);x.fill();}
function cluster(x,ty,px,py,s,pal){x.save();x.translate(px,py);x.scale(s,s);disc(x,0,12,56,24);
 if(ty===0){blk(x,-38,-6,30,30,PAL.white);dome(x,-23,-6,15,pal);blk(x,6,-30,26,54,PAL.white);dome(x,19,-30,13,pal);dark(x,-29,8,12,16);dark(x,12,0,12,20);}
 else if(ty===1){blk(x,-36,-4,30,26,PAL.cream);shp(x,[[-41,-4],[-21,-26],[-1,-4]],pal[1]);shp(x,[[-41,-4],[-21,-26],[-24,-26],[-44,-4]],pal[0]);blk(x,6,-14,28,36,PAL.tan);shp(x,[[1,-14],[20,-34],[39,-14]],pal[1]);shp(x,[[1,-14],[20,-34],[17,-34],[-2,-14]],pal[0]);dark(x,-26,6,10,16);dark(x,15,4,10,18);}
 else if(ty===2){blk(x,-42,12,84,10,PAL.stone,3);for(let i=0;i<3;i++){const hw=28-i*6,y=12-i*20;blk(x,-hw+4,y-16,2*hw-8,16,PAL.red,3);dark(x,-4,y-12,8,10);shp(x,[[-hw-14,y-12],[-hw+3,y-27],[hw-3,y-27],[hw+14,y-12],[hw+2,y-8],[-hw-2,y-8]],'#ffbd3f');shp(x,[[-hw-14,y-12],[-hw+3,y-27],[-hw+3,y-23],[-hw-8,y-12]],'#fff1a4');}box(x,-1.5,-74,3,16,'#ffbd3f',1);ball(x,0,-76,4,PAL.gold);}
 else if(ty===4){blk(x,-38,6,76,12,PAL.stone,3);x.save();x.beginPath();x.rect(-40,-40,80,48);x.clip();ball(x,0,8,30,PAL.white);x.restore();blk(x,-9,-32,18,10,PAL.cream,2);shp(x,[[-3,-32],[0,-52],[3,-32]],'#ffbd3f');shp(x,[[0,-52],[14,-48],[0,-44]],pal[1]);dark(x,-5,8,10,10);}
 x.restore();}
function palm(x,px,py,h,t,ph){x.save();x.translate(px,py);const sw=Math.sin(t*1.3+ph)*3;x.strokeStyle='#b4723c';x.lineWidth=6;x.lineCap='round';x.beginPath();x.moveTo(0,0);x.quadraticCurveTo(4,-h/2,sw,-h);x.stroke();x.translate(sw,-h);for(let i=0;i<6;i++){x.save();x.rotate((i-2.5)*.62+Math.sin(t*1.7+ph+i)*.04);oval(x,0,-17,6,19,i%2?'#2fbf86':'#38e08e');x.restore();}ball(x,0,0,4,PAL.orange);x.restore();}
function oasis(x,s,t,full){x.save();x.translate(640,360);x.scale(s,s);disc(x,0,40,98,36);
 const wg=x.createLinearGradient(20,56,76,76);wg.addColorStop(0,'#a4fbef');wg.addColorStop(1,'#1d64b0');oval(x,46,67,38,13,'#e9ad66');x.fillStyle=wg;x.beginPath();x.ellipse(46,67,33,9.5,0,0,TAU);x.fill();x.strokeStyle='rgba(255,255,255,.6)';x.lineWidth=1.5;x.beginPath();x.ellipse(46+Math.sin(t*2)*4,67,10+Math.sin(t*2.5)*2,3,0,0,TAU);x.stroke();
 palm(x,-92,40,66,t,0);palm(x,-70,46,50,t,1.7);
 box(x,-62,-30,4,64,'#7a4a28',2);box(x,58,-30,4,64,'#7a4a28',2);
 for(let i=0;i<8;i++){const x0=-66+i*16.5;x.fillStyle=i%2?'#fff0cc':'#ff5d8f';x.beginPath();x.moveTo(x0,-42);x.lineTo(x0+16.5,-42);x.lineTo(x0+16.5,-28);x.quadraticCurveTo(x0+8.2,-20,x0,-28);x.closePath();x.fill();}
 box(x,-66,-45,132,6,'#ffd23f',3);
 blk(x,-46,16,92,9,PAL.wood,3);box(x,-46,15,92,3,'#ff8fb4',1);box(x,-42,24,5,22,'#7a4a28',2);box(x,38,24,5,22,'#7a4a28',2);
 if(full){oval(x,-26,10,7,6,'#c98a54');oval(x,32,10,6,6,'#d97a4a');bundle(x,6,7,.8);
  box(x,80,-6,3,34,'#7a4a28',1);box(x,128,-6,3,34,'#7a4a28',1);for(let i=0;i<4;i++){x.fillStyle=i%2?'#fff0cc':'#56e8ff';x.beginPath();x.moveTo(78+i*13.5,-12);x.lineTo(91.5+i*13.5,-12);x.lineTo(91.5+i*13.5,-2);x.quadraticCurveTo(84.7+i*13.5,3,78+i*13.5,-2);x.fill();}blk(x,82,22,50,6,PAL.wood,2);}
 x.restore();}
function bundle(x,cx,cy,s){x.save();x.translate(cx,cy);x.scale(s,s);const g=x.createLinearGradient(-11,-8,11,8);g.addColorStop(0,'#ffe9be');g.addColorStop(1,'#d9a15f');x.fillStyle=g;rr(x,-11,-8,22,16,5);x.fill();x.fillStyle='#ff5d8f';rr(x,-2.5,-8,5,16,2);x.fill();rr(x,-11,-2.5,22,5,2);x.fill();x.beginPath();x.ellipse(-4,-10,4,2.5,-.4,0,TAU);x.ellipse(4,-10,4,2.5,.4,0,TAU);x.fill();x.restore();}
function sb(x,p,s,unf,a,t){if(a<=.01)return;x.save();x.globalAlpha*=a;x.translate(p[0],p[1]);x.scale(s,s);glow(x,0,0,34,'#ff5d8f',.35);const w=24+unf*24,ph=Math.sin(t*3)*2*unf,g=x.createLinearGradient(-w/2,-9,w/2,9);g.addColorStop(0,'#ffb4dc');g.addColorStop(.5,'#f35b9c');g.addColorStop(1,'#aa3f88');x.fillStyle=g;x.beginPath();x.moveTo(-w/2,-9);x.bezierCurveTo(-w/6,-9-7*unf+ph,w/6,-9+7*unf-ph,w/2,-9);x.lineTo(w/2,9);x.bezierCurveTo(w/6,9+7*unf-ph,-w/6,9-7*unf+ph,-w/2,9);x.closePath();x.fill();x.strokeStyle='#ffce82';x.lineWidth=2;x.lineCap='round';for(const k of [-3,3]){x.beginPath();x.moveTo(-w/2+2,k);x.bezierCurveTo(-w/6,k-7*unf+ph,w/6,k+7*unf-ph,w/2-2,k);x.stroke();}x.restore();}
function idea(x,p,s,a,t){if(a<=.01)return;x.save();x.globalAlpha*=a;x.translate(p[0],p[1]+Math.sin(t*2.2)*2);x.scale(s,s);glow(x,0,0,38,'#56e8ff',.35);x.fillStyle='rgba(210,245,255,.16)';rr(x,-15,-19,30,38,6);x.fill();x.strokeStyle='#56e8ff';x.lineWidth=2.6;x.setLineDash([6,4]);x.stroke();x.setLineDash([]);x.lineWidth=2.4;x.lineCap='round';for(let i=0;i<4;i++){x.beginPath();x.moveTo(-8,-9+i*8);x.lineTo(i===3?0:8,-9+i*8);x.stroke();}spark(x,15,-19,7+2*Math.sin(t*4),'#fff',1);x.restore();}
function person(x,px,py,s,o){x.save();x.translate(px,py);x.scale(s,s);x.fillStyle='rgba(8,6,40,.35)';x.beginPath();x.ellipse(0,1,13,4,0,0,TAU);x.fill();
 const g=x.createLinearGradient(-10,-30,10,0);g.addColorStop(0,o.robe[0]);g.addColorStop(1,o.robe[1]);
 if(o.hand){const hx=(o.hand[0]-px)/s,hy=(o.hand[1]-py)/s;x.strokeStyle=o.robe[1];x.lineWidth=4.5;x.lineCap='round';x.beginPath();x.moveTo(6,-24);x.lineTo(hx,hy);x.stroke();ball(x,hx,hy,3.2,SK);}
 x.fillStyle=g;x.beginPath();x.moveTo(-7,-28);x.quadraticCurveTo(0,-32,7,-28);x.lineTo(12,0);x.lineTo(-12,0);x.closePath();x.fill();
 x.fillStyle=H.rgba(o.robe[2],.4);x.beginPath();x.moveTo(3,-29);x.lineTo(7,-28);x.lineTo(12,0);x.lineTo(5,0);x.fill();
 box(x,-9,-14,18,4,o.sash||'#ffd23f',2);
 if(!o.hand){x.strokeStyle=o.robe[1];x.lineWidth=4.5;x.lineCap='round';x.beginPath();x.moveTo(6,-24);x.lineTo(10,-9);x.stroke();}
 ball(x,0,-37,8,SK);
 if(o.hat==='turban'){x.fillStyle=o.hc;x.beginPath();x.ellipse(0,-41,9.5,6.5,0,Math.PI,TAU);x.fill();box(x,-9.5,-42,19,4,o.hc,2);}
 else if(o.hat==='cone'){shp(x,[[-12,-42],[0,-56],[12,-42]],o.hc);}
 x.fillStyle=C0;oval(x,-3,-37,1.2,1.4,C0);oval(x,3,-37,1.2,1.4,C0);x.restore();}
const C0='#141846';
const RA=['#7ad9ff','#3c8fd6','#1d4f96'],RB=['#ffb26b','#ff8d3f','#b24a2a'],RC=['#c6a4ff','#8b5cff','#4d2ba8'],RM=['#ffcf6a','#ff9a3c','#c4571f'],RT=['#9bf0d0','#38b98e','#1d6f66'];
function camel(x,a,b,s,t,ph,dir){x.save();x.translate(a,b+Math.sin(t*6+ph)*1.4);x.scale(s*dir,s);oval(x,0,0,72,38,'#e9ad66');ball(x,-32,-28,26,PAL.tan);ball(x,25,-29,27,PAL.tan);box(x,51,-89,22,94,'#efbd79',10);oval(x,69,-91,29,18,'#f5c98c');for(const p of [-48,-20,24,48])box(x,p,17,12,70,'#d38b4b',6);box(x,-33,-18,65,38,'#d75179',8);box(x,-23,-15,45,8,'#ffcb68',3);bundle(x,-4,-54,2.6);oval(x,80,-94,3,4,C0);x.strokeStyle='#d38b4b';x.lineWidth=9;x.lineCap='round';x.beginPath();x.moveTo(-65,-1);x.quadraticCurveTo(-93,-20,-91,13);x.stroke();x.restore();}
function ov(x,t,P,solid,tin,tout,col){const a=seg(t,tin,tin+.3)*(1-seg(t,tout,tout+.7));if(a<=0)return;const pr=eo(seg(t,tin,tin+1));if(solid)arrow(x,P,pr,col,8,{head:false,a});else{arrow(x,P,pr,'#16225e',10,{dots:true,head:false,a:a*.7});arrow(x,P,pr,col,6,{dots:true,head:false,a});}}
function jpos(t){const u1=eio(seg(t,37.4,39.8)),u2=eio(seg(t,40.5,41.7)),u3=eio(seg(t,41.7,43.2));if(t<40.1)return bez(gp('S','O'),u1);if(t<41.7)return bez(gp('O','E1'),u2);return bez(gp('E1','C'),.82*u3);}
function world(x,t,c){
 const bg=x.createRadialGradient(640,370,40,640,370,640);bg.addColorStop(0,'rgba(120,90,220,.28)');bg.addColorStop(1,'rgba(60,40,140,0)');x.fillStyle=bg;x.fillRect(-500,-400,2300,1500);
 for(const e of ED){const P=EP[e[0]+e[1]],pr=eo(seg(t,e[3],e[3]+e[4]));let al=.8;if(e[0]+e[1]==='W1W3')al=1-.7*seg(t,18.3,19.6)*.9;arrow(x,P,pr,'#c4b5ff',6,{dots:true,head:false,a:al});}
 // overland highlight
 const hl=[['C','E1'],['E1','O'],['O','M1'],['M1','W2'],['W2','W1']],ha=1-seg(t,18,19.3);
 if(ha>0)hl.forEach((e,i)=>{const pr=eo(seg(t,13.6+i*.5,14.1+i*.5));const P=gp(e[0],e[1]);arrow(x,P,pr,'#ff5d8f',9,{head:false,a:.55*ha});arrow(x,P,pr,'#ffd23f',4.5,{dots:true,head:false,a:ha});});
 // halo
 const hu=seg(t,c1[2],c1[2]+2.4);if(hu>0){const C=N.C;glow(x,C[0],C[1],lerp(60,230,eo(hu)),'#ffb86b',.3-.12*seg(t,13,16));x.save();x.strokeStyle=H.rgba('#ffcf8a',.55*(1-hu));x.lineWidth=3;x.setLineDash([2,9]);x.lineCap='round';x.beginPath();x.arc(C[0],C[1],lerp(40,210,eo(hu)),0,TAU);x.stroke();x.restore();}
 // s2 segments
 const A4=seg(t,29.9,30.2)*(1-seg(t,c2[4],c2[4]+1));
 if(A4>0){const Pw=gp('M1','O'),Pe=gp('O','E1');arrow(x,Pw,eo(seg(t,29.9,30.9)),'#ff5d8f',8,{head:false,a:A4});arrow(x,Pe,eo(seg(t,30.4,31.4)),'#ff5d8f',8,{head:false,a:A4});
  x.save();x.globalAlpha*=A4;const w=bez(Pw,.5),e=bez(Pe,.5);camel(x,w[0],w[1]-14,.28,t,0,1);camel(x,e[0],e[1]-14,.28,t,1,1);x.strokeStyle='#ffd23f';x.lineWidth=4;x.setLineDash([2,8]);x.lineCap='round';x.beginPath();x.arc(640,360,44+3*Math.sin(t*4),0,TAU);x.stroke();x.restore();}
 const emph=eo(seg(t,c3[4],c3[4]+1.1)),hue={W1:'#52d0cf',O:'#ffb86b',C:'#ff6a7a'};
 const so=lerp(.55,1,seg(c.z,1,1.7));
 for(const id of Object.keys(ND)){const d=ND[id],p=N[id],na=back(seg(t,d.nt,d.nt+.6));if(na<=0)continue;const iE=!!hue[id],m=1+.2*emph*(iE?1:0);x.save();x.globalAlpha*=Math.min(1,na)*(1-.5*emph*(iE?0:1));
  glow(x,p[0],p[1],70*d.s,'#ffd23f',.16);if(iE&&emph>0)glow(x,p[0],p[1],110,hue[id],.4*emph);
  if(id==='O'){x.save();x.translate(640,360);x.scale(m,m);x.translate(-640,-360);oasis(x,so,t,c.z>1.5&&t>20);x.restore();}else cluster(x,d.ty,p[0],p[1],d.s*na*m,d.pal);x.restore();}
 // s1 people
 const pa=1-seg(t,18,19);if(t<20&&pa>0){x.save();x.globalAlpha*=pa;
  const hA=kf(t,[[.3,[748,322]],[1,[752,312]],[1.5,[752,310]],[2.5,[776,304]],[3,[748,322]]]),hB=kf(t,[[.3,[800,312]],[1.8,[796,302]],[2.5,[792,298]],[3.2,[792,298]],[3.8,[800,316]]]);
  person(x,742,336,1,{robe:RA,hat:'turban',hc:'#ffd23f',hand:hA});person(x,802,314,1,{robe:RB,hat:'turban',hc:'#ff5d8f',hand:hB});
  const bp=kf(t,[[.96,[752,310]],[1.5,[752,306]],[2.5,[790,299]],[3.2,[792,298]]]);bundle(x,bp[0],bp[1]-6,1.1);
  const hp=seg(t,2.4,2.9)*(1-seg(t,2.9,3.6));glow(x,790,298,40,'#ffd23f',.5*hp);x.restore();}
 // market
 const za=seg(c.z,1.7,2.4);
 if(t>S2&&za>0){x.save();x.globalAlpha*=za;
  let h1,h2,h3=[740,392],bp=null;
  if(t<S3){h1=kf(t,[[22,[600,392]],[22.68,[606,382]],[23.4,[606,372]],[24.1,[624,376]],[24.8,[630,380]],[25.8,[606,392]],[26,[606,392]]]);
   h2=kf(t,[[22,[656,392]],[23.3,[646,384]],[24.1,[640,380]],[24.8,[636,380]],[25.8,[662,382]],[27.5,[662,382]],[28,[672,380]],[29,[664,392]]]);
   h3=kf(t,[[27,[738,394]],[27.9,[734,384]],[28.9,[740,382]],[30,[740,392]]]);
   bp=kf(t,[[23.1,[648,384]],[24.1,[638,380]],[24.8,[616,382]],[25.8,[606,390]]]);
   const ba=seg(t,23.1,23.5);
   for(const [px,py,dr,ph] of [[468,424,1,0],[522,436,1,1.3],[806,424,-1,.6],[858,438,-1,2]]){const off=(1-eo(seg(t,21.2,22.6)))*130*-dr;camel(x,px+off,py,.5,t,ph,dr);}
   person(x,590,410,1,{robe:RA,hat:'turban',hc:'#ffd23f',hand:h1});person(x,654,410,1,{robe:RB,hat:'turban',hc:'#ff5d8f',hand:h2});person(x,744,410,1,{robe:RC,hat:'cone',hc:'#ffd23f',hand:h3});
   if(ba>0)bundle(x,bp[0],bp[1],1.2*ba);}
  else{h1=kf(t,[[47.12,[606,392]],[47.4,[606,384]],[48,[622,378]],[48.8,[640,380]],[49.4,[606,392]]]);h2=kf(t,[[47.12,[656,392]],[48,[648,382]],[48.8,[648,380]],[49.4,[660,392]]]);
   person(x,590,410,1,{robe:RA,hat:'turban',hc:'#ffd23f',hand:h1});person(x,654,410,1,{robe:RB,hat:'turban',hc:'#ff5d8f',hand:h2});person(x,744,410,1,{robe:RC,hat:'cone',hc:'#ffd23f'});}
  x.restore();}
 // silk
 const wide=1-seg(c.z,1,2.5),ss=.9*(1+1.1*wide);
 if(t<c2[6]){const p=kf(t,[[22.68,[606,382]],[23.4,[606,372]],[24.1,[624,376]],[24.8,[634,380]],[25.8,[662,382]],[27.5,[662,382]],[27.9,[672,378]],[28.9,[740,382]],[29.44,[740,382]],[31,[668,424]]]);
  sb(x,p,ss,eio(seg(t,23,23.8))*(1-eio(seg(t,24.9,25.8))),seg(t,22.5,22.9)*(1-seg(t,c2[4],c2[4]+1)),t);}
 const Pw=gp('O','W3'),Pi=gp('E1','C'),mw=bez(Pw,.5),mi=bez(Pi,.5);
 ov(x,t,Pw,true,c2[6],S3+.1,'#ff5d8f');ov(x,t,Pw,true,57.3,62.2,'#ff5d8f');ov(x,t,Pi,false,44.6,S3+.6,'#56e8ff');ov(x,t,Pi,false,57.6,62.2,'#56e8ff');
 sb(x,[mw[0],mw[1]-20],1.8,0,seg(t,c2[6]+.1,c2[6]+.6)*(1-seg(t,S3,S3+.4))*(t<S3+1?1:0),t);
 if(t>=S3){const p=kf(t,[[47.3,[606,384]],[48,[622,378]],[48.8,[652,380]],[49.4,[662,382]]]);sb(x,p,ss,eio(seg(t,47.3,48))*(1-eio(seg(t,48.8,49.4)))*.8,seg(t,S3+.2,S3+.5)*(1-seg(t,50,50.6)),t);
  sb(x,[mw[0],mw[1]-20],1.8,0,seg(t,57.3,57.8)*(1-seg(t,62.2,63)),t);}
 // idea
 const jp=jpos(t),mov=(t>37.4&&t<39.8)||(t>40.5&&t<43.2),ap=seg(t,c2[4]+.1,c2[4]+.7);
 ov(x,t,gp('S','O'),false,33.3,46,'#56e8ff');
 const ta=seg(t,37.3,37.7)*(1-seg(t,44.3,45.1));
 if(ta>0){arrow(x,gp('S','O'),eio(seg(t,37.4,39.8)),'#56e8ff',5,{dots:true,a:ta});arrow(x,gp('O','E1'),eio(seg(t,40.5,41.7)),'#56e8ff',5,{dots:true,a:ta});arrow(x,gp('E1','C'),eio(seg(t,41.7,43.2)),'#56e8ff',5,{dots:true,a:ta});
  const bb=mov?Math.abs(Math.sin(t*7))*3:0;x.save();x.globalAlpha*=ta;person(x,jp[0]-16,jp[1]+10-bb,1.15,{robe:RM,sash:'#ff5d8f'});person(x,jp[0]+18,jp[1]+12-bb*.7,1.15,{robe:RT,hat:'cone',hc:'#ffd23f'});x.restore();}
 if(t<S3){idea(x,[jp[0],jp[1]-60],1.5*back(ap),Math.min(1,ap)*(1-seg(t,44.3,44.8)),t);idea(x,[mi[0],mi[1]-22],1.5,seg(t,44.6,45.2)*(1-seg(t,S3,S3+.8)),t);}
 else idea(x,[mi[0],mi[1]-22],1.5,seg(t,57.6,58.1)*(1-seg(t,62.2,63)),t);
 // s3 handoffs
 [['W1','W2',52.1],['E1','C',53],['W3','O',53.9],['E2','C',54.8],['O','M1',55.7]].forEach(h=>{const u=seg(t,h[2],h[2]+1.1),a=seg(t,h[2],h[2]+.2)*(1-seg(t,h[2]+.95,h[2]+1.25));if(a<=0)return;const P=gp(h[0],h[1]),p=bez(P,lerp(.25,.75,eio(u)));x.save();x.globalAlpha*=a;glow(x,...bez(P,.25),26,'#ffd23f',.5*(1-u));glow(x,...bez(P,.75),30,'#ffd23f',.55*u*u);bundle(x,p[0],p[1]-6,1.7);x.restore();});
}
function lab(x,t,c,txt,bg,wp,wins,px){let a=0,s=0;for(const w of wins){const aa=seg(t,w[0],w[0]+.4)*(1-seg(t,w[1]-.5,w[1]));if(aa>a){a=aa;s=back(seg(t,w[0],w[0]+.5));}}if(a<=.01)return;const sx=cl(640+(wp[0]-c.cx)*c.z,190,1090),sy=360+(wp[1]-c.cy)*c.z;pill(x,sx,sy,txt,px||30,{bg,s:Math.max(.01,s),a});}
function screen(x,t,c){
 pill(x,170,38,'Schematic network',28,{bg:'#ffffff',a:seg(t,.3,.8)});
 lab(x,t,c,'Han China','#ffd23f',[1105,205],[[9.7,20.3]]);
 lab(x,t,c,'Central Asia','#ffffff',[640,448],[[13.7,20.3],[37.5,45.4]]);
 lab(x,t,c,'Lands farther west','#ff8fb4',[185,305],[[14.8,20.3]]);
 lab(x,t,c,'China','#ffd23f',[1105,205],[[37.6,45.4]]);
 lab(x,t,c,'South Asia','#56e8ff',[560,668],[[37.45,45.4]]);
 const mw=bez(gp('O','W3'),.5),mi=bez(gp('E1','C'),.5);
 lab(x,t,c,'Goods','#ff8fb4',[mw[0],mw[1]-70],[[44.9,47.1]]);
 lab(x,t,c,'Ideas','#56e8ff',[mi[0],mi[1]-72],[[45.1,47.1]]);
 const oa=seg(t,S2+.6,S2+1)*(1-seg(t,c2[3],c2[3]+.5));if(oa>0)pill(x,640,78,'Central Asian oasis',38,{bg:'#ffd23f',s:back(seg(t,S2+.6,S2+1.1)),a:oa});
 const da=seg(t,9.6,10.1)*(1-seg(t,14.3,14.9));if(da>0)text(x,'2nd century BCE',640,100+(1-eo(seg(t,9.6,10.2)))*14,52,'#ffffff',{a:da});
 const oc=seg(t,c3[2],c3[2]+.5)*(1-seg(t,55.5,56));if(oc>0)text(x,'Over centuries',640,100,52,'#ffdd83',{a:oc});
 const cd=seg(t,62.4,63.2);if(cd>0)text(x,'Connected, distinct',640,96+(1-eo(cd))*14,58,'#ffffff',{a:cd});
}
window.explainer=function(x,W,H_,t){const c=cam(t);sky(x,W,H_,t,{x:(c.cx-640)*.5,y:(c.cy-360)*.5,z:Math.pow(c.z,.4)});x.save();x.translate(640,360);x.scale(c.z,c.z);x.translate(-c.cx,-c.cy);world(x,t,c);x.restore();screen(x,t,c);};
const ACT={s01:['Two settlements exchange a ribbon-wrapped bundle along a dotted path','Pull back as branches draw on one at a time into a network','Han China halo and date label appear','Dotted overland links trace left through the oasis to lands farther west','Alternate link appears, an older branch recedes; whole web held'],s02:['Push into the oasis market with two caravans','Silk unfolds and is handed to the receiving trader','Same silk bolt passes to a third person','Pull back to two separate route segments with a handoff at the oasis','Silk recedes; outlined idea symbol appears at South Asia','Monk and traveler carry the idea eastward in local steps to China','Silk and idea sit on separate links; travelers and arrows clear'],s03:['Brief return to the silk handoff at the oasis','Pull back into the wider network','Staggered local handoffs at several nodes; Over centuries','Silk and idea traced on separate short links','Three distinct clusters emphasized; Connected, distinct']};
window.cueEvents=[];[['s01',0,c1],['s02',S2,CT.s02],['s03',S3,CT.s03]].forEach(([id,st,arr])=>arr.forEach((v,i)=>window.cueEvents.push({scene_id:id,cue_id:id+'_c'+(i+1),at_sec:id==='s01'?v:st+v-(id==='s02'?0:0),action:ACT[id][i]})));
window.cueEvents.forEach(e=>{if(e.scene_id==='s02')e.at_sec=+(CT.s02[+e.cue_id.slice(-1)-1]+S2).toFixed(3);if(e.scene_id==='s03')e.at_sec=+(CT.s03[+e.cue_id.slice(-1)-1]+S3).toFixed(3);});
const VP=(s,t,comp,objs,cam,cont,tr,snd)=>({scene_id:s,at_sec:t,composition:comp,objects:objs,camera:cam,continuity:cont,transition:tr,sounds:snd});
window.visualPlan=[
VP('s01',1.5,'Close elevated view of two settlements; bundle with pink ribbon passes between traders',['settlement-nodes','goods-bundle','silk-ribbon'],'Close hold','Opening','Object-led',['dry pluck at handoff']),
VP('s01',6.5,'Pull back; branches draw on one at a time',['route-network','settlement-nodes'],'Pullback','Original exchange shrinks into the web','Camera pullback',['filtered air']),
VP('s01',10.8,'Han China glow halo and date label',['han-china','route-network'],'Push toward China','Same network','Camera drift',['low tone']),
VP('s01',15,'Pink and yellow overland link traced left through the oasis',['central-oasis','silk-ribbon','route-network'],'Track left','Same network','Tracking',['soft ticks']),
VP('s01',19,'Whole web with alternate link; old branch recedes',['route-network','central-oasis'],'Wide','Oasis stays prominent','Begin push',['resolving pluck']),
VP('s02',22,'Oasis market close-up with caravans',['central-oasis','caravan-groups','oasis-traders'],'Push into oasis','Same node changes scale','Push-in',['paper texture']),
VP('s02',25,'Silk handed to receiving trader',['oasis-traders','silk-ribbon','goods-bundle'],'Medium hold','Same oasis','None',['cloth rustle']),
VP('s02',28.5,'Silk passes to third person',['oasis-traders','silk-ribbon'],'Hold','Same oasis','None',['muted pluck']),
VP('s02',31.5,'Wide web with two separate route segments and handoff at oasis',['route-network','caravan-groups','silk-ribbon'],'Pullback','Silk follows','Pullback',['air']),
VP('s02',34,'Idea symbol at South Asia node',['idea-symbol','south-asia-node'],'Wide','Web retained','Cross-fade',['high pluck']),
VP('s02',40,'Monk and traveler carry idea eastward',['idea-symbol','south-asia-node','route-network'],'Gentle pan','Same web','Tracking',['tonal accent']),
VP('s02',45,'Silk and idea on separate links',['silk-ribbon','idea-symbol'],'Wide','Journey markers clear','Settle',['tick']),
VP('s03',48.5,'Push to oasis, brief silk handoff',['oasis-traders','silk-ribbon','central-oasis'],'Modest push','Same oasis','Push',['cloth rustle']),
VP('s03',54,'Staggered local handoffs across the wide network',['route-network','settlement-nodes'],'Locked wide','Same web','None',['pluck']),
VP('s03',59,'Silk and idea on separate short links',['silk-ribbon','idea-symbol','route-network'],'Locked','Same web','None',['plucks']),
VP('s03',63.5,'Three distinct clusters with Connected, distinct',['settlement-nodes','route-network','central-oasis'],'Locked hold','Markers cleared','Hold to silence',['resolving chord'])];
window.scoreSound=function(k){
 const P=(f,t,g,d)=>k.tone(t,{f,type:'triangle',dur:d||.5,gain:g,a:.004,verb:.3});
 P('E5',2.45,.16);k.play('whoosh',c1[1],{dur:1.8,gain:.22,top:1400});k.tone(c1[2],{f:'C3',dur:1.8,gain:.13,a:.3,verb:.3});
 P('G5',13.6,.1);P('A5',14.3,.1);P('C6',15,.1);P('C6',c1[4],.14,.8);P('G5',c1[4]+.12,.1,.8);
 k.play('whoosh',19.7,{dur:1.2,gain:.18});k.play('paper',c2[0],{dur:.5,gain:.4});k.play('paper',c2[1],{dur:.45,gain:.5});P('G4',24.6,.08,.3);P('D5',28.6,.12);
 k.play('whoosh',c2[3],{dur:2,gain:.22,top:1200});P('A6',c2[4],.08,.7);P('D5',39.8,.08,.4);P('E5',43.2,.13,1.2);P('B4',43.2,.08,1.2);k.play('tick',c2[6],{gain:.4});
 k.play('paper',c3[0],{dur:.4,gain:.4});k.play('whoosh',c3[1],{dur:1.4,gain:.18});P('G5',c3[2]+.1,.12);P('E5',c3[3],.1);P('A5',c3[3]+.5,.1);
 ['C4','E4','G4','C5'].forEach((n,i)=>k.tone(c3[4]+i*.04,{f:n,type:'sine',dur:2.6,gain:.07,a:.05,verb:.4}));};