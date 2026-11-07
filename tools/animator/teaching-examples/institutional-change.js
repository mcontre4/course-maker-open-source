(function () {
  "use strict";
  const C = { ink:"#141846", white:"#fff9ef", cyan:"#56e8ff", yellow:"#ffd23f", pink:"#ff789f", violet:"#8b5cff", muted:"#c4bee7", teal:["#a4fbef","#3ccbdc","#1d64b0"], tan:["#ffe9be","#ecb676","#b4723c"] };
  const A=[0,6.56,10.8,13.12,19.6,24.64,29.28];
  const B=[36.56,36.56+4.64,36.56+8.24,36.56+11.88,36.56+17.84,36.56+27.04,36.56+30.72,36.56+34,36.56+37.04];
  const D=[77.44,77.44+4.56,77.44+8.987,77.44+14.24,77.44+19.96,77.44+26.96,77.44+31.067,77.44+35.04];
  const clamp=H.clamp, mix=H.lerp, TAU=Math.PI*2;
  const p=(t,a,d=1)=>clamp((t-a)/d);
  const e=(t,a,d=1)=>H.ease.inOut(p(t,a,d));
  const out=(t,a,d=1)=>H.ease.out(p(t,a,d));
  const visible=(t,a,b)=>out(t,a,.35)*(1-out(t,b,.3));
  function group(x,a,fn){if(a<=0)return;x.save();x.globalAlpha*=clamp(a);fn();x.restore();}
  function rect(x,a,b,w,h,col,r=12){x.fillStyle=col;FV.rr(x,a,b,w,h,r);x.fill();}
  function poly(x,points,col){x.fillStyle=col;x.beginPath();points.forEach((q,i)=>i?x.lineTo(q[0],q[1]):x.moveTo(q[0],q[1]));x.closePath();x.fill();}
  function oval(x,a,b,rx,ry,col){x.fillStyle=col;x.beginPath();x.ellipse(a,b,rx,ry,0,0,TAU);x.fill();}
  function line(x,points,col,w=4){x.strokeStyle=col;x.lineWidth=w;x.lineCap="round";x.lineJoin="round";x.beginPath();points.forEach((q,i)=>i?x.lineTo(...q):x.moveTo(...q));x.stroke();}
  function grad(x,a,b,c,d,cols){const g=x.createLinearGradient(a,b,c,d);cols.forEach((s,i)=>g.addColorStop(i/(cols.length-1),s));return g;}
  function txt(x,s,a,b,size=32,col=C.white,opt={}){FV.text(x,s,a,b,size,col,opt);}
  function pill(x,s,a,b,size=28,col=C.yellow,alpha=1){FV.pill(x,a,b,s,size,{bg:col,a:alpha});}
  function head(x,s,sub,alpha=1,col=C.white){
    group(x,alpha,()=>{txt(x,s,640,109,46,col);if(sub)txt(x,sub,640,157,29,C.muted,{w:700});});
  }
  function shadow(x,a,b,rx=65,ry=13){oval(x,a,b,rx,ry,"rgba(5,6,35,.33)");}
  function person(x,a,b,s=1,o={}){
    x.save();x.translate(a,b);x.scale(s,s);
    const skin=o.skin||["#f8c68f","#ce8e61","#89583f"];
    const coat=o.coat||["#9cefe6","#37b7c4","#226484"];
    shadow(x,0,1,40,9);
    rect(x,-25,-66,21,64,"#252b59",9);rect(x,5,-66,21,64,"#303563",9);
    rect(x,-29,-8,28,12,"#121735",5);rect(x,3,-8,29,12,"#121735",5);
    x.fillStyle=grad(x,-38,-113,38,-40,coat);
    x.beginPath();x.moveTo(-40,-43);x.lineTo(-37,-98);x.quadraticCurveTo(-32,-120,-12,-121);x.lineTo(12,-121);x.quadraticCurveTo(35,-116,38,-98);x.lineTo(41,-43);x.quadraticCurveTo(0,-34,-40,-43);x.fill();
    poly(x,[[20,-115],[38,-97],[41,-43],[23,-40]],coat[2]);
    line(x,[[-29,-103],[-31,-63]],"rgba(255,255,255,.25)",3);
    rect(x,-9,-135,18,25,skin[1],7);
    if(o.jacket){poly(x,[[-17,-121],[0,-100],[17,-121],[10,-68],[-11,-68]],"#fff0d5");poly(x,[[0,-103],[6,-94],[2,-64],[-5,-94]],"#705b93");}
    const gesture=o.gesture||0;
    line(x,[[-32,-104],[-45,-77],[-48-gesture*12,-61-gesture*32]],coat[1],16);
    line(x,[[32,-104],[46,-77],[47+gesture*11,-60-gesture*36]],coat[1],16);
    FV.ball(x,-48-gesture*12,-59-gesture*32,9,skin,{sha:.25});
    FV.ball(x,47+gesture*11,-59-gesture*36,9,skin,{sha:.25});
    oval(x,-26,-151,7,10,skin[1]);oval(x,26,-151,7,10,skin[1]);
    FV.ball(x,0,-157,29,skin,{sha:.23,rima:.25});
    if(o.curls){
      for(let i=0;i<8;i++){const ang=Math.PI+i*Math.PI/7;oval(x,Math.cos(ang)*25,-165+Math.sin(ang)*20,11,11,"#24203b");}
      oval(x,-23,-159,7,13,"#24203b");
    } else {
      x.fillStyle=o.gray?"#aab2cb":"#28243b";x.beginPath();x.moveTo(-27,-157);x.quadraticCurveTo(-38,-191,-6,-190);x.quadraticCurveTo(35,-195,28,-153);x.lineTo(17,-172);x.quadraticCurveTo(-8,-166,-16,-176);x.closePath();x.fill();
    }
    oval(x,-10,-155,2.4,3,"#29223c");oval(x,10,-155,2.4,3,"#29223c");
    line(x,[[0,-151],[-2,-143],[3,-142]],skin[2],2);
    line(x,[[-7,-134],[5,-135]],"#795046",2);
    if(o.glasses){
      x.strokeStyle="#252947";x.lineWidth=2.7;
      FV.rr(x,-22,-162,18,14,5);x.stroke();FV.rr(x,4,-162,18,14,5);x.stroke();
      line(x,[[-4,-156],[4,-156]],"#252947",2.7);
    }
    if(o.officer){
      rect(x,-31,-184,62,13,grad(x,-25,-184,25,-170,["#c6d0ae","#7b927a","#4d655c"]),5);
      poly(x,[[-31,-172],[30,-172],[38,-165],[-29,-165]],"#344e4c");
      rect(x,-31,-113,18,7,"#c2cfac",2);rect(x,14,-113,18,7,"#c2cfac",2);
      rect(x,-17,-89,13,15,"#71887b",2);rect(x,6,-89,13,15,"#71887b",2);
      rect(x,-35,-54,72,7,"#3b514e",2);
    }
    x.restore();
  }
  const writer={skin:["#e5ad7b","#ba7c52","#794c38"],coat:["#ffe18b","#d9ab49","#9d692e"],curls:true};
  const reader={skin:["#bd875e","#966345","#624131"],coat:["#9ae9df","#38aebc","#236681"],glasses:true};
  const officer={skin:["#f0c194","#c4936b","#8c654a"],coat:["#b6c4a3","#7f9783","#465e58"],officer:true};
  const civilian={skin:["#d7a276","#ad7754","#78523e"],coat:["#a4b9ee","#5a76b0","#334b7a"],jacket:true,gray:true};

  function lectern(x,a,b,s=1){
    x.save();x.translate(a,b);x.scale(s,s);
    shadow(x,0,5,100,18);
    x.fillStyle=grad(x,-80,-155,85,0,["#91e6e4","#429fb9","#345681"]);
    x.beginPath();x.moveTo(-88,-152);x.quadraticCurveTo(0,-173,88,-152);x.lineTo(65,-9);x.quadraticCurveTo(0,9,-65,-9);x.closePath();x.fill();
    poly(x,[[47,-158],[88,-152],[65,-9],[37,-5]],"#29466f");
    poly(x,[[-88,-152],[-67,-159],[-49,-14],[-65,-9]],"rgba(200,255,245,.25)");
    rect(x,-96,-164,192,24,grad(x,-90,-170,95,-140,["#b8fff0","#63cdd4","#397991"]),9);
    FV.ball(x,0,-89,28,["#fff0ac","#d7bc6b","#8c754c"],{sha:.22});
    oval(x,0,-89,17,17,"#607e93");oval(x,0,-89,11,11,"#aacbd0");
    rect(x,-73,-10,146,17,"#263f70",7);
    line(x,[[42,-166],[45,-190],[33,-202]],"#a2c5d4",5);oval(x,32,-204,9,5,"#263956");
    x.restore();
  }
  function assembly(x,a,b,s=1,closed=0){
    x.save();x.translate(a,b);x.scale(s,s);
    shadow(x,0,84,160,26);
    oval(x,0,26,163,92,"#333866");
    oval(x,0,15,156,84,"#555380");
    for(let row=0;row<3;row++){
      const rx=72+row*35,ry=34+row*19;
      for(let i=0;i<7;i++){
        const ang=Math.PI*.12+i*Math.PI*.76/6;
        const xx=Math.cos(ang)*rx,yy=-Math.sin(ang)*ry+29+row*10;
        rect(x,xx-13,yy-22,26,25,"#7c76b2",7);
        x.save();x.translate(xx,yy);x.rotate((ang-Math.PI/2)*.18);
        rect(x,-19,-6,38,19,grad(x,-15,-5,20,18,["#c2b5d7","#9183b0","#685e91"]),5);
        poly(x,[[-9,-5],[4,-4],[6,3],[-8,3]],"#e9e1e8");x.restore();
      }
    }
    rect(x,-16,16,32,36,"#5eb7ca",6);rect(x,-22,12,44,10,"#a4e5e4",4);
    rect(x,-110,75,220,18,"#706b99",7);
    line(x,[[-141,76],[-141,-22]],"#8d85b6",8);line(x,[[141,76],[141,-22]],"#8d85b6",8);
    if(closed>0){
      x.save();x.beginPath();x.rect(-145,-28,290*closed,108);x.clip();
      rect(x,-143,-22,286,98,"rgba(29,32,67,.78)",6);
      for(let i=-135;i<=135;i+=27)rect(x,i,-21,9,99,grad(x,i,-20,i+9,65,["#b7a8ce","#7e739e","#514a79"]),4);
      rect(x,-144,-25,288,11,"#baa8cd",4);rect(x,-144,68,288,11,"#74648c",4);x.restore();
    }
    x.restore();
  }
  function newspaper(x,a,b,s=1,redact=0){
    x.save();x.translate(a,b);x.scale(s,s);
    x.fillStyle=grad(x,-70,-50,75,65,["#fff4d6","#e7dfce","#b8b8bc"]);
    FV.rr(x,-75,-53,150,106,5);x.fill();
    line(x,[[0,-42],[0,43]],"#adaeb8",2);
    rect(x,-59,-39,116,10,"#777d93",2);
    for(let row=0;row<6;row++){
      for(let col=0;col<2;col++){
        const xx=-59+col*65,yy=-19+row*10;
        rect(x,xx,yy,row===5?35:48,2.8,"#9496a1",1);
      }
      const u=clamp(redact*7-row*.8);
      if(u>0)rect(x,-61,-21+row*10,123*u,7,"#26304c",1);
    }
    x.restore();
  }
  function decree(x,a,b,s=1,title=1,subtitle=true){
    x.save();x.translate(a,b);x.scale(s,s);
    shadow(x,3,140,105,12);
    rect(x,-111,-136,222,272,"#77728a",12);
    rect(x,-116,-143,222,272,grad(x,-100,-140,100,125,["#fff8df","#e8e0c8","#c6c1b9"]),10);
    poly(x,[[73,-143],[106,-110],[73,-110]],"#b7b9b4");
    group(x,title,()=>{
      txt(x,"1968",0,-107,34,"#544a70",{shadow:"transparent"});
      txt(x,"AI-5",0,-44,67,C.ink,{shadow:"transparent"});
      if(subtitle){txt(x,"Institutional",0,15,26,C.ink,{shadow:"transparent"});txt(x,"Act No. 5",0,45,26,C.ink,{shadow:"transparent"});}
    });
    for(let i=0;i<3;i++)rect(x,-76,77+i*13,145-i*15,4,"#aaa79f",2);
    x.restore();
  }
  function ballotBox(x,a,b,s,t){
    x.save();x.translate(a,b);x.scale(s,s);
    shadow(x,0,56,77,13);
    rect(x,-64,-43,128,103,grad(x,-60,-40,65,58,["#8bf1e5","#4395b1","#354e83"]),13);
    rect(x,-52,-30,104,76,"#6eafc4",9);
    rect(x,-44,-22,88,60,"rgba(207,255,245,.28)",6);
    line(x,[[-38,30],[-38,-14],[28,-14]],"rgba(226,255,251,.7)",3);
    rect(x,-70,-57,140,23,"#a7ebe6",8);rect(x,-26,-50,52,7,"#243e64",3);
    const ins=out(t,A[0],1.15),wy=mix(-149,-25,ins);
    if(t<2){
      x.save();x.beginPath();x.rect(-90,-250,180,200);x.clip();
      rect(x,-23,wy,46,64,"#fff4cf",4);
      line(x,[[-11,wy+23],[-2,wy+32],[14,wy+12]],"#3b8094",4);x.restore();
      group(x,1-out(t,.95,.65),()=>{
        rect(x,10,wy-13,105,24,"#d6a477",11);
        rect(x,0,wy-8,40,17,"#efc295",8);
        rect(x,18,wy-1,25,17,"#efc295",7);
      });
    }
    if(t>=1.1)poly(x,[[-20,-20],[22,-13],[12,21],[-29,14]],"#e9ead5");
    x.restore();
  }

  const cameras=[
    [0,2.7,610,348,1],
    [A[2],1.1,610,350,1],
    [A[4],2.3,660,350,1.08],
    [A[5],.9,660,340,1.2],
    [A[6],1.5,610,350,1],
    [B[0],1.6,660,320,1.38],
    [B[2],1.4,610,350,1],
    [B[3],1.3,300,357,1.65],
    [B[4],1.6,650,345,1.12],
    [B[5],1.3,990,414,1.48],
    [B[6],.85,925,465,2.15],
    [B[7],1.1,985,418,1.55],
    [B[8],2.3,985,408,1.64],
    [D[0],3.1,650,355,1.02],
    [D[1],1.7,680,360,1],
    [D[2],1.2,625,355,.97],
    [D[3],1.6,660,345,1.18],
    [D[4],1.3,680,365,1.02],
    [D[5],.8,655,355,1],
    [D[6],1.8,650,355,.97],
    [D[7],1.8,650,355,.93]
  ];
  function camera(t){
    let q={x:230,y:350,z:2.25};
    for(const k of cameras){
      if(t<k[0])break;
      const u=e(t,k[0],k[1]);
      const n={x:mix(q.x,k[2],u),y:mix(q.y,k[3],u),z:mix(q.z,k[4],u)};
      if(t<k[0]+k[1])return n;
      q={x:k[2],y:k[3],z:k[4]};
    }
    return q;
  }
  function projection(cam,a,b){return [640+(a-cam.x)*cam.z,353+(b-cam.y)*cam.z];}
  function attached(x,cam,s,a,b,col=C.yellow,size=28,alpha=1){
    const q=projection(cam,a,b);pill(x,s,q[0],q[1],size,col,alpha);
  }
  function world(x,t){
    const endShift=e(t,D[6],1.8),lx=mix(660,850,endShift);
    const peopleShift=e(t,D[6],1.8),wx=mix(910,330,peopleShift),rx=mix(1060,500,peopleShift);
    const closed=out(t,B[2],1.35)*(1-out(t,D[2],3));
    const humanity=out(t,B[5],1.1);
    const barrier=out(t,B[7],1.2),easing=out(t,D[1],3.1);
    const officerIn=out(t,A[4],2.2),civilianIn=out(t,D[3],2.7);
    oval(x,640,462,567,92,"rgba(63,71,125,.28)");
    oval(x,640,449,553,81,"rgba(102,102,163,.17)");
    x.save();x.globalAlpha=.24;line(x,[[135,467],[1110,467]],"#a9a0db",2);x.restore();
    group(x,1-humanity*.76,()=>assembly(x,300,350,1,closed));
    if(t>=B[2] && t<B[5]){
      const u=out(t,B[2],.8);
      FV.arrow(x,[[615,360],[530,340],[472,334],[440,361]],u,C.pink,5,{dots:true});
      if(t>=B[2]+.7){
        rect(x,476,329,43,40,"#24224e",8);
        line(x,[[481,342],[490,352]],C.pink,4);line(x,[[505,342],[514,352]],C.pink,4);
      }
    }
    group(x,1-humanity*.74,()=>{
      if(t<A[4]+2.6){
        group(x,1-out(t,A[4],2.2),()=>{
          person(x,660-170*out(t,A[4],2.2),365,1,civilian);
        });
      }
      if(t>=A[4]){
        group(x,officerIn*(1-civilianIn),()=>{
          person(x,mix(940,lx,officerIn)-100*civilianIn,365,1,officer);
        });
        const supportAlpha=officerIn*(1-out(t,A[5],1.4))*.85;
        group(x,supportAlpha,()=>{
          person(x,795,387,.8,{coat:["#ecc0d5","#a273a6","#69527e"],skin:["#b17b57","#8e593f","#65402e"],gesture:.5});
          person(x,865,386,.78,{coat:["#c7cae6","#969bbd","#5d6389"],skin:C.tan,jacket:true});
        });
      }
      if(t>=D[3])group(x,civilianIn,()=>person(x,lx+100*(1-civilianIn),365,1,civilian));
      lectern(x,lx,485,1.06);
    });
    if(t>=B[0] && t<B[5]+.5){
      const enter=out(t,B[0],1.2),small=e(t,B[2],1.25);
      group(x,(1-out(t,B[5],.45))*enter,()=>{
        decree(x,660,mix(400,310,enter)+small*33,mix(.42,1,enter)*(1-small*.54),out(t,B[1],.4),t<B[4]);
      });
    }
    const publicIntro=out(t,.8,1.5);
    group(x,publicIntro,()=>{
      group(x,1-humanity*.7,()=>{
        person(x,1138,469,.7,{skin:C.tan,coat:["#e4c6ec","#aa85c4","#655285"],gesture:.25});
        person(x,1000,440,.68,{skin:["#e9b78f","#bc865e","#82553e"],coat:["#b1bfdc","#7887ae","#4b577d"],gray:true});
      });
      person(x,wx,526,.94,writer);
      person(x,rx,526,.94,reader);
      if(t>=B[5]){
        const deskA=out(t,B[5],.65),nx=mix(928,370,peopleShift);
        group(x,deskA,()=>{
          rect(x,nx-83,490,14,48,"#514c7b",4);rect(x,nx+67,490,14,48,"#514c7b",4);
          rect(x,nx-95,480,190,16,grad(x,nx-95,480,nx+95,495,["#a4a4c7","#76779e","#4e527e"]),6);
          newspaper(x,nx,462,.88,out(t,B[6],1.9));
        });
      }
      if(barrier>0){
        const bx=mix(983,426,peopleShift),gateY=331;
        const spread=mix(0,58,easing);
        group(x,barrier*(1-endShift*.75),()=>{
          for(let i=0;i<5;i++){
            const xx=bx+(i-2)*19+(i<2?-spread:spread);
            rect(x,xx,gateY,7,(526-gateY)*barrier,grad(x,xx,gateY,xx+7,526,["#c7b8d7","#807895","#514b72"]),3);
          }
          line(x,[[bx-42-spread,gateY],[bx+43+spread,gateY]],"#a497b8",7);
        });
      }
      if(t>=D[1]&&t<D[6]){
        const u=out(t,D[1],1.7),pa=1-out(t,D[3],1.5);
        group(x,u*pa,()=>{
          person(x,mix(1230,1140,u),496,.86,{skin:C.tan,coat:["#ffaebd","#d57491","#8c4b75"],gesture:.7});
          person(x,mix(1300,1210,u),510,.86,{skin:["#b98156","#96603f","#65412e"],coat:["#c3c1ec","#8f8bc5","#585a93"],curls:true});
          rect(x,1104,273,6,119,"#c4b2a4",3);rect(x,994,254,231,58,"#ffe4a0",10);
          txt(x,"Democracy",1109,282,29,C.ink,{shadow:"transparent"});
        });
      }
    });
    if(t<D[3]){
      const boxRetire=out(t,A[1],1),scale=mix(.9,.58,boxRetire);
      group(x,1-out(t,B[0],1.3),()=>ballotBox(x,230-60*boxRetire,430+25*boxRetire,scale,t));
    }
    if(t< A[2]){
      const broken=out(t,A[1],.7),u=out(t,1.45,1.5);
      FV.arrow(x,[[288,420],[365,402],[485,391],[555,377]],u*(1-broken*.56),C.cyan,6,{dots:true,head:broken<.3});
      group(x,broken,()=>{line(x,[[410,382],[426,405]],C.pink,5);line(x,[[435,382],[451,405]],C.pink,5);});
    }
    if(t>=A[3]&&t<A[4]+1){
      const context=out(t,A[3],.8)*(1-out(t,A[4],.8));
      group(x,context,()=>{
        person(x,442,333,.68,{skin:C.tan,coat:["#e7bee7","#b586bb","#795389"],gesture:.85});
        person(x,828,332,.68,{skin:["#ba865f","#956344","#624531"],coat:["#c1d1eb","#8597c0","#59688d"],gesture:.7});
      });
    }
    if(t>=D[4]){
      const seam=out(t,D[4],1.3);
      group(x,seam,()=>{
        line(x,[[mix(863,275,peopleShift),538],[mix(932,378,peopleShift),528],[mix(946,408,peopleShift),539],[mix(1008,557,peopleShift),529]],"#c8b2ca",2.5);
        line(x,[[mix(863,275,peopleShift),545],[mix(932,378,peopleShift),535],[mix(946,408,peopleShift),546],[mix(1008,557,peopleShift),536]],"#181b46",3);
      });
    }
  }
  function timeline(x,t){
    const alpha=out(t,A[2],.6);
    group(x,alpha,()=>{
      rect(x,70,571,1140,141,"rgba(12,13,45,.8)",24);
      const full=out(t,A[6],2.4);
      const end=mix(140,990,full);
      line(x,[[140,620],[990,620]],"#514c7a",3);
      if(full>0)line(x,[[140,620],[end,620]],C.violet,13);
      line(x,[[140,607],[140,633]],C.yellow,5);
      txt(x,"1964",140,674,64,C.white);
      if(t>=A[6]){
        group(x,out(t,A[6],.5),()=>{
          line(x,[[990,607],[990,633]],C.yellow,5);
          txt(x,"1985",990,674,64,C.white);
          txt(x,"Military dictatorship",565,590,28,C.muted);
        });
      }
      if(t>=B[0]){
        const at=140+(990-140)*4/21,aa=out(t,B[0],.5);
        group(x,aa,()=>{
          line(x,[[at,607],[at,635]],C.pink,4);
          txt(x,"1968",at,674,54,t<D[0]?C.pink:C.muted);
          if(t<D[0])FV.glow(x,at,620,35,C.pink,.32);
        });
      }
      if(t>=D[2]&&t<D[6]){
        const u=out(t,D[2],1.5),clear=1-out(t,D[6],.4);
        group(x,clear,()=>{
          line(x,[[615,559],[615,550],[615+(990-615)*u,550],[615+(990-615)*u,559]],C.cyan,3);
          txt(x,"Gradual transition",803,526,29,C.cyan);
          const marker=mix(680,990,e(t,D[2],D[3]-D[2]+1));
          oval(x,marker,620,10,10,C.yellow);
        });
      }
      if(t>=D[4]){
        const u=out(t,D[4],1);
        line(x,[[1001,620],[1001+169*u,620]],"#b8bad4",3);
      }
      if(t>=D[7]){
        group(x,out(t,D[7],.65),()=>{
          txt(x,"Longer process",1100,590,28,C.white);
          line(x,[[1168,620],[1178,615]],"#b8bad4",3);
          line(x,[[1168,620],[1178,625]],"#b8bad4",3);
        });
      }
    });
  }
  function memory(x,t){
    const aa=visible(t,D[5],D[6]);
    group(x,aa,()=>{
      rect(x,87,184,529,339,"rgba(15,18,58,.96)",24);
      x.strokeStyle="#9284b4";x.lineWidth=2;FV.rr(x,87,184,529,339,24);x.stroke();
      pill(x,"AI-5 · 1968",350,215,30,C.pink);
      x.save();x.translate(120,266);
      assembly(x,95,87,.52,1);
      person(x,350,94,.58,officer);lectern(x,350,163,.64);
      decree(x,238,87,.31,1,false);
      FV.arrow(x,[[305,113],[263,120],[225,118],[194,119]],out(t,D[5],.7),C.pink,4,{dots:true});
      x.restore();
      const emph=out(t,D[5],.7);
      txt(x,"Concentrated power",350,457,31,C.white,{a:emph});
      txt(x,"Curtailed freedoms",350,494,31,C.pink,{a:out(t,D[5]+1.1,.6)});
      line(x,[[302,537],[302,563]],C.pink,2);
    });
  }
  function annotations(x,t,cam){
    pill(x,t<A[2]?"CIVIC LIFE":"BRAZIL",123,34,24,C.white);
    if(t>=A[2])txt(x,"Institutional schematic",1238,35,28,C.muted,{align:"right",w:700});
    if(t<A[1]){
      head(x,"Elections",t<2.7?"People choose civilian leaders":"An electoral route to authority",out(t,0,.35));
      attached(x,cam,"Civilian leadership",660,519,C.cyan,28,out(t,1.6,.7));
    } else if(t<A[2]){
      head(x,"Coup","Unlawful seizure of power",out(t,A[1],.45),C.pink);
    } else if(t<A[4]){
      head(x,"Brazil · 1964",null,out(t,A[2],.4));
      attached(x,cam,"João Goulart",660,515,C.white,30,1-out(t,A[4],.3));
      attached(x,cam,"Elected president",660,552,C.cyan,28,1-out(t,A[4],.3));
      if(t>=A[3]){
        const aa=out(t,A[3],.5);
        attached(x,cam,"Proposed reforms",340,175,C.yellow,28,aa);
        attached(x,cam,"Cold War fears",896,175,C.pink,28,out(t,A[3]+.6,.5));
        group(x,out(t,A[3]+1.2,.5),()=>txt(x,"Fears of communism",961,241,28,C.muted));
      }
    } else if(t<A[5]){
      head(x,"A change imposed on civilian authority",null,out(t,A[4],.4));
      group(x,1-out(t,A[4],1.7),()=>{
        const q=projection(cam,660-250*out(t,A[4],1.7),518);
        pill(x,"João Goulart",q[0],q[1],29,C.white);
      });
      group(x,out(t,A[4],.7),()=>txt(x,"Military + civilian supporters",640,167,29,C.muted));
    } else if(t<B[0]){
      head(x,t<A[6]?"Military rule":"Brazil’s military dictatorship",null);
      attached(x,cam,"Military rule",660,530,C.cyan,30,1);
    } else if(t<B[2]){
      head(x,t<B[1]?"A decree within the dictatorship":"AI-5 · 1968",null,out(t,B[0],.4));
      group(x,out(t,B[1],.5),()=>{
        txt(x,"Institutional Act No. 5",1014,315,31,C.white);
        txt(x,"Schematic document",1014,358,28,C.muted,{w:700});
      });
    } else if(t<B[3]){
      head(x,"Power to close Congress","And further restrict rights",out(t,B[2],.4));
      attached(x,cam,"Congress",300,215,C.white,30);
      attached(x,cam,"Closed",300,467,C.pink,29,out(t,B[2],.4));
      attached(x,cam,"Rights restricted",1007,554,C.pink,28,out(t,B[2]+.7,.6));
    } else if(t<B[4]){
      head(x,"Congress","A lawmaking body",out(t,B[3],.35));
      attached(x,cam,"Closed",300,467,C.pink,29);
      group(x,out(t,B[3]+.9,.5),()=>{
        txt(x,"A weakened check",1015,313,30,C.white);
        txt(x,"on presidential power",1015,355,28,C.muted);
      });
    } else if(t<B[5]){
      head(x,"Power concentrated in the presidency",null,out(t,B[4],.4));
      attached(x,cam,"Presidency",660,532,C.cyan,31,out(t,B[4],.5));
      attached(x,cam,"Congress · closed",300,236,C.pink,28);
      group(x,out(t,B[4]+1,.6),()=>txt(x,"Fewer protections for people",1007,242,29,C.muted));
    } else if(t<B[6]){
      head(x,"Repression","State power to silence or punish opposition",out(t,B[5],.4));
    } else if(t<B[7]){
      head(x,"Censorship","Restrictions on publishing and speech",out(t,B[6],.35));
    } else if(t<D[0]){
      head(x,"Imprisonment and torture",t<B[8]?null:"Human harms — not just government procedure",1,C.white);
    } else if(t<D[1]){
      const fade=1-out(t,D[0],1.3);
      head(x,"Imprisonment and torture",null,fade);
      group(x,out(t,D[0]+1.4,.5),()=>head(x,"Not one sudden reversal",null,1));
    } else if(t<D[2]){
      head(x,"Gradual easing · public pressure",null,out(t,D[1],.4));
    } else if(t<D[3]){
      head(x,"A transition over time",null,out(t,D[2],.35));
    } else if(t<D[4]){
      head(x,"1985", "A civilian president takes office",out(t,D[3],.4));
      attached(x,cam,"Civilian presidency",660,530,C.cyan,30,out(t,D[3],1.5));
    } else if(t<D[5]){
      head(x,"An important change, not complete resolution",null,out(t,D[4],.35));
      attached(x,cam,"Civilian presidency",660,514,C.cyan,28);
      group(x,out(t,D[4],.55),()=>pill(x,"Legacies of repression",995,544,28,C.white));
    } else if(t<D[6]){
      head(x,"What AI-5 reveals",null,out(t,D[5],.3));
      pill(x,"Civilian presidency",991,244,28,C.cyan);
    } else {
      head(x,"Civilian rule returned. Legacies remained.",null,out(t,D[6],.4));
      const u=e(t,D[6],1.8);
      attached(x,cam,"Civilian presidency",mix(660,850,u),527,C.cyan,28);
      group(x,out(t,D[6],.6),()=>pill(x,"Legacies of repression",383,536,28,C.white));
    }
  }

  window.explainer=function(ctx,W,H_,t){
    ctx.save();ctx.scale(W/1280,H_/720);
    FV.sky(ctx,1280,720,t*.06,{x:t*.55,y:0,z:1});
    // A quiet institutional setting, not a map or an archival reconstruction.
    rect(ctx,0,180,1280,382,"rgba(14,17,54,.36)",0);
    const cam=camera(t);
    ctx.save();ctx.translate(640,353);ctx.scale(cam.z,cam.z);ctx.translate(-cam.x,-cam.y);
    world(ctx,t);
    ctx.restore();
    annotations(ctx,t,cam);
    timeline(ctx,t);
    memory(ctx,t);
    ctx.restore();
  };

  const actions=[
    ["s01",A,[
      "Lower a ballot through the slot; pull back to voters and a dotted electoral connection.",
      "Break the electoral connection and withdraw the ballot box; define an unlawful seizure of power.",
      "Identify Brazil and 1964; attach João Goulart / Elected president to the shared lectern.",
      "Stage concurrent discussions of proposed reforms and Cold War fears of communism.",
      "Move military authority and civilian supporters into the civic space; remove Goulart's nameplate.",
      "Settle military authority at the lectern and label Military rule.",
      "Extend the bounded Military dictatorship interval from 1964 to 1985."
    ]],
    ["s02",B,[
      "Mark 1968 on the existing timeline and raise a schematic decree from the lectern.",
      "Reveal AI-5, Institutional Act No. 5 and 1968 on the decree.",
      "Draw the decree's authority link, close Congress and restrict the public's space.",
      "Track to the same closed assembly to identify its lawmaking function.",
      "Pull back to the enlarged presidency and the broken congressional check.",
      "Track to the writer and reader; bring the publication desk forward and define repression.",
      "Push into the newspaper and sequentially cover article lines with censorship strips.",
      "Pull back to the recurring adults; close a sparse barrier and label imprisonment and torture.",
      "Push gently toward the separated people and hold their human harms without resolution."
    ]],
    ["s03",D,[
      "Carry the separated people forward and slowly reconnect the civic space; no sudden reversal.",
      "Advance a small democracy group while the public barrier eases separately and gradually.",
      "Draw an undated Gradual transition bracket and move emphasis toward 1985.",
      "Replace the military presidential role with a generic civilian officeholder, without election imagery.",
      "Retain the censored newspaper and add a metaphorical floor seam for legacies of repression.",
      "Recall AI-5 in a clearly bounded 1968 historical inset, distinct from the civilian presidency.",
      "Clear the historical inset and recompose the public left and civilian presidency right.",
      "Continue a thin neutral timeline beyond the 1985 military-rule endpoint; hold Longer process."
    ]]
  ];
  window.cueEvents=[];
  actions.forEach(([scene,times,descs])=>times.forEach((at,i)=>window.cueEvents.push({
    scene_id:scene,cue_id:scene+"_c"+String(i+1).padStart(2,"0"),at_sec:at,action:descs[i]
  })));
  function shot(scene,at,composition,objects,camera,continuity,transition,sounds=[]){
    return {scene_id:scene,at_sec:at,composition:composition,objects:objects,camera:camera,continuity:continuity,transition:transition,sounds:sounds};
  }
  const civic=["presidential-lectern","congress-assembly","public-group","historical-timeline"];
  window.visualPlan=[
    shot("s01",.8,"Close ballot, hand and transparent-front ballot box; the general electoral principle.",["ballot-box","electoral-link","presidential-lectern"],"Pull back from the ballot as it lowers.","Establish the shared civic objects.","Object-led pullback, not a historical election.",["Quiet paper brush at ballot insertion."]),
    shot("s01",4.6,"Voters connect through the ballot box to civilian leadership.",["ballot-box","electoral-link","public-group","presidential-lectern"],"Settled elevated wide view.","The box remains in the same civic space.","Continuous reveal of the electoral relationship."),
    shot("s01",8.6,"A broken dotted route leaves a clear gap for the definition of a coup.",["ballot-box","electoral-link","presidential-lectern"],"Hold the wide civic relationship.","Withdraw rather than destroy the ballot box.","The connection breaks because authority is seized.",["Muted low tap at the break."]),
    shot("s01",16.7,"Goulart's lectern lies between concurrent reform and Cold War discussions.",civic.concat(["goulart-nameplate","context-discussions"]),"Medium-wide elevated institutional schematic.","Identify Brazil and keep the lectern recognizable.","Historical reframing; old electoral labels cleared."),
    shot("s01",22.4,"Military authority and civilian supporters replace the elected president at the lectern.",civic.concat(["goulart-nameplate","military-authority","civilian-supporters"]),"Small lateral follow and shallow push.","The nameplate visibly exits; there is no vote transfer.","Authority changes within the same setting."),
    shot("s01",33.8,"Military authority above a bounded 1964–1985 interval.",civic.concat(["military-authority","ballot-box"]),"Pull back to the whole period and hold.","Lectern, assembly and public persist into AI-5.","Continuous timeline attention, no wipe.",["Soft low structural tone at military-rule placement."]),
    shot("s02",39,"A schematic decree is brought forward from the military lectern.",civic.concat(["military-authority","ai5-decree"]),"Track attention to 1968 and push toward the paper.","The period's endpoints do not move.","The document provides a closer view of the same institutions.",["Soft paper placement at 1968."]),
    shot("s02",43.3,"AI-5 and Institutional Act No. 5 are large on the illustrated sheet.",["ai5-decree","presidential-lectern","historical-timeline"],"Document close-medium view.","Decree retains its identity in subsequent wide shots.","Quiet reading hold.",["Restrained low pluck at the AI-5 title."]),
    shot("s02",47.1,"A decree-linked gate closes Congress while rights are restricted.",civic.concat(["ai5-decree","congress-gate","institutional-link"]),"Pull back for the relationship.","The assembly retains curved desks behind its gate.","Draw the relationship before settling the restriction.",["Subdued closing tap."]),
    shot("s02",51.5,"Close three-quarter schematic of congressional desks, papers and a closed foreground gate.",["congress-assembly","congress-gate","historical-timeline"],"Track and push into the assembly, preserving closed status.","A close view, not a reopening event.","Retire decree subtitle before changing focus."),
    shot("s02",58.2,"Presidency dominates the disconnected assembly and the public.",civic.concat(["military-authority","institutional-link","congress-gate"]),"Return to a deliberately asymmetric institutional wide view.","AI-5 remains on the lectern.","Hold the concentration of power.",["Very quiet low tonal emphasis."]),
    shot("s02",65.1,"A mustard-shirted writer and teal-jacketed reader become the focus.",["writer","reader","publication-desk","censored-newspaper","presidential-lectern"],"Track from institutions to the people.","Public figures were already present; institutional layers recede.","A meaningful shift from procedure to its human effects."),
    shot("s02",68.9,"Opaque strips sequentially cover schematic newspaper article lines.",["writer","publication-desk","censored-newspaper"],"Push into the paper.","Same newspaper, no fabricated quotations.","Censorship is shown as an action on publication.",["Faint dry paper scrape."]),
    shot("s02",75.6,"Writer and reader separated by a sparse barrier; imprisonment and torture named soberly.",["writer","reader","censored-newspaper","public-barrier","historical-timeline"],"Pull back, then slowly push toward the interrupted human relationship.","No harm is depicted graphically or erased.","Quiet human-centered hold; continue into the next narration scene."),
    shot("s03",79.9,"The inherited human scene slowly reconnects to the full civic setting.",civic.concat(["writer","reader","public-barrier"]),"Slow pullback.","Keep the barrier and censored paper; retire harm labels cleanly.","No instant revolution or restorative wipe."),
    shot("s03",84.9,"A small democracy group advances while a separate barrier easing opens more public space.",civic.concat(["writer","reader","public-barrier","democracy-placard"]),"Modest lateral tracking with the public.","Publication remains censored as a historical trace.","Distinct staggered developments express gradual change.",["Very soft filtered-air texture."]),
    shot("s03",89.3,"An undated bracket over the later timeline emphasizes gradual transition toward 1985.",civic.concat(["democracy-placard","public-barrier"]),"Return to a stable wide composition and lower timeline.","Do not invent a transition starting date.","Hold bracket and endpoint together."),
    shot("s03",95.6,"A generic civilian officeholder takes the same presidential lectern in 1985.",civic.concat(["civilian-president","military-authority"]),"Rise from timeline to lectern and push slightly in.","Military authority exits; no ballot or direct-election inference.","Calm role replacement.",["A quiet two-note resolving interval, not a fanfare."]),
    shot("s03",100,"Civilian presidency coexists with serious public figures, a censored paper and metaphorical floor seam.",civic.concat(["civilian-president","writer","reader","censored-newspaper","legacy-seam"]),"Ease back to include institutions and people.","The human consequences do not vanish at 1985.","Retain unresolved traces; label Legacies of repression."),
    shot("s03",106.1,"A bounded AI-5 · 1968 memory inset recalls concentrated power and curtailed freedoms.",["ai5-decree","congress-gate","military-authority","civilian-president","historical-timeline"],"Locked current scene with a separate historical inset.","Current civilian presidency stays visibly separate.","Historical recall is explicitly dated and then retired."),
    shot("s03",114.8,"Final wide tableau: public left, civilian presidency right; thick military-rule band ends at 1985 and a thin line continues.",civic.concat(["civilian-president","writer","reader","censored-newspaper","legacy-seam"]),"Gentle final pullback into a stable hold.","Retain the newspaper and metaphorical seam, without implying recovery.","No outgoing wipe; distinguish institutional change from a longer process.",["Quiet warm sustained resolving tone, then silence."])
  ];
  window.scoreSound=function(k){
    k.play("paper",A[0],{gain:.14,dur:.32,minor:true,pan:-.25});
    k.tone(A[1],{f:115,type:"sine",dur:.19,gain:.055,minor:true});
    k.tone(A[5],{f:"D3",type:"triangle",dur:.6,gain:.045,a:.05,minor:true});
    k.play("paper",B[0],{gain:.17,dur:.34,minor:true});
    k.tone(B[1],{f:"A3",type:"triangle",dur:.35,gain:.045,minor:true});
    k.tone(B[2],{f:[[0,155],[.2,94]],type:"sine",dur:.27,gain:.045,minor:true,pan:-.3});
    k.tone(B[4],{f:"D3",type:"sine",dur:.65,a:.06,gain:.033,minor:true});
    k.noise(B[6],{dur:.55,color:"pink",filter:"bandpass",f:1500,q:.6,gain:.024,a:.08,minor:true});
    k.noise(D[1],{dur:1.1,color:"pink",filter:"lowpass",f:850,gain:.016,a:.25,minor:true});
    k.tone(D[3],{f:"D4",type:"triangle",dur:.9,a:.08,gain:.036,minor:true,verb:.1});
    k.tone(D[3],{f:"A4",type:"sine",dur:1.1,a:.14,gain:.024,minor:true,verb:.1});
    k.tone(D[7],{f:"D4",type:"sine",dur:2.6,a:.25,gain:.035,minor:true,verb:.16});
    k.tone(D[7],{f:"A4",type:"sine",dur:2.5,a:.32,gain:.017,minor:true,verb:.12});
  };
  window.DURATION=116.4;
})();