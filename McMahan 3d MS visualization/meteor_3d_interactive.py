"""Interactive 3-D ellipsoid + meteor-path explorer with live Doppler (all math runs in the page's JS).
Writes meteor_3d_interactive.html.  Frame: origin = ground at baseline midpoint, x East, y North, z Up (km);
it is an exact rigid transform of ECEF, so distances/angles are true.  WDPN 54.309441 MHz -> RX."""
import json
import numpy as np
import meteor_doppler_wdpn as m
from plotly.offline import get_plotlyjs

T, R = m.ecef(*m.TX), m.ecef(*m.RX)
g0 = m.point_on_path(0.5, 0)
E0, N0, U0 = m.enu(g0[0], g0[1])
O = m.ecef(g0[0], g0[1], 0)
loc = lambda p: [float(((np.asarray(p) - O) / 1e3) @ a) for a in (E0, N0, U0)]
ldir = lambda v: [float(np.asarray(v) @ a) for a in (E0, N0, U0)]
C = loc([0, 0, 0])
K = dict(T=loc(T), R=loc(R), C=C, Z=ldir([0, 0, 1]), RE=float(np.linalg.norm(C)), LAM=float(m.LAM))

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meteor Scatter 3D</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--card:#f3f4f6;--ok:#1a7f37;--bad:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#14161a;--fg:#e6e6e6;--mut:#9aa0a6;--card:#1f2329;--ok:#4cc26a;--bad:#ff7b72}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif}
#wrap{display:flex;flex-wrap:wrap;gap:12px;padding:10px}
#ctl{flex:0 0 300px;background:var(--card);border-radius:8px;padding:12px}
#plots{flex:1 1 600px;min-width:320px}
label{display:flex;justify-content:space-between;margin-top:8px}label b{font-weight:600}
input[type=range]{width:100%}
button{margin:4px 4px 0 0;padding:4px 8px;border:1px solid var(--mut);background:var(--bg);color:var(--fg);border-radius:5px;cursor:pointer}
#fd{font-size:26px;font-weight:700;margin:6px 0 2px}.ok{color:var(--ok)}.bad{color:var(--bad)}
small{color:var(--mut)}h1{font-size:15px;margin:0 0 6px}
</style></head><body><div id="wrap">
<div id="ctl"><h1>WDPN 54.31 MHz → RX forward scatter</h1>
<div id="fd">–</div><div id="fdinfo"><small></small></div>
<div>Presets:<br><button data-p="q">¼ from RX</button><button data-p="m">Midpoint</button><button data-p="t">¼ from TX</button></div>
<label>Reflection point along path <b id="vx"></b></label><input id="x" type="range" min="-105" max="105" step="1" value="-52">
<label>Offset from path (+ = NW) <b id="vy"></b></label><input id="y" type="range" min="-250" max="250" step="5" value="0">
<label>Altitude <b id="vh"></b></label><input id="h" type="range" min="70" max="130" step="1" value="100">
<label>Heading (direction of travel, from N) <b id="vaz"></b></label><input id="az" type="range" min="0" max="359" step="1" value="240">
<label>Descent below horizontal <b id="vd"></b></label><input id="d" type="range" min="0" max="90" step="0.1" value="14.5">
<label>Speed <b id="vv"></b></label><input id="v" type="range" min="11" max="72" step="1" value="20">
<div><button id="snap">Set descent for 0 Hz at this heading</button></div>
<div><label style="justify-content:flex-start;gap:6px"><input id="ex" type="checkbox"> vertical exaggeration ×2</label></div>
<div style="margin-top:8px"><small>Blue shell = surface of equal TX→P→RX path length through the reflection point (the 0 Hz "tangent" surface for that point). Green path: |f<sub>D</sub>| ≤ 100 Hz at P; red: outside. Convention: + Hz = path shortening. Straight-line paths, no refraction. Ground curvature is real.</small></div>
</div>
<div id="plots"><div id="g3" style="height:560px"></div><div id="g2" style="height:240px"></div></div></div>
<script>__PLOTLY__</script>
<script>
const K=__K__; const D2R=Math.PI/180;
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]],add=(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]],sc=(a,s)=>[a[0]*s,a[1]*s,a[2]*s];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2],cr=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const nrm=a=>Math.sqrt(dot(a,a)),un=a=>sc(a,1/nrm(a));
const T=K.T,R=K.R,Z=K.Z;
const t0=un(sub(T,R)).map((v,i)=>v); const up0=[0,0,1];
const tb=un(sub(sub(T,R),sc(up0,dot(sub(T,R),up0)))), sd=cr(up0,tb);
function frame(P){const up=un(sub(P,K.C));const e=un(cr(Z,up));const n=cr(up,e);return{up,e,n}}
function place(x,y,h){const P0=add(sc(tb,x),sc(sd,y));return add(K.C,sc(un(sub(P0,K.C)),K.RE+h))}
function vel(P,az,d){const f=frame(P),a=az*D2R,dd=d*D2R;
  return add(add(sc(f.e,Math.cos(dd)*Math.sin(a)),sc(f.n,Math.cos(dd)*Math.cos(a))),sc(f.up,-Math.sin(dd)))}
function bis(P){return add(un(sub(P,T)),un(sub(P,R)))}
function fD(P,v,vkms){return -(vkms*1000/K.LAM)*dot(v,bis(P))}
function ellipsoid(P){const S=nrm(sub(P,T))+nrm(sub(P,R)),c=sc(add(T,R),.5),ax=un(sub(T,R)),f=nrm(sub(T,R))/2,a=S/2,b=Math.sqrt(a*a-f*f);
  const e1=un(cr(ax,[0,0,1])),e2=cr(ax,e1),nt=50,np_=72,X=[],Y=[],Zz=[];
  for(let i=0;i<=nt;i++){const th=Math.PI*i/nt,rx=X[i]=[],ry=Y[i]=[],rz=Zz[i]=[];
    for(let j=0;j<=np_;j++){const ph=2*Math.PI*j/np_;
      const p=add(add(c,sc(ax,a*Math.cos(th))),sc(add(sc(e1,Math.cos(ph)),sc(e2,Math.sin(ph))),b*Math.sin(th)));
      const under=nrm(sub(p,K.C))<K.RE;rx.push(under?null:p[0]);ry.push(under?null:p[1]);rz.push(under?null:p[2]);}}
  return{X,Y,Zz,S,a,b}}
// ground
const GX=[],GY=[],GZ=[];for(let i=0;i<=44;i++){GX[i]=[];GY[i]=[];GZ[i]=[];for(let j=0;j<=44;j++){const x=-330+15*j,y=-330+15*i;GX[i].push(x);GY[i].push(y);GZ[i].push(Math.sqrt(K.RE*K.RE-x*x-y*y)-K.RE)}}
const col=s=>[[0,s],[1,s]];
const tr=[
 {type:'surface',x:GX,y:GY,z:GZ,showscale:false,opacity:.25,colorscale:col('#556b2f'),hoverinfo:'skip',name:'ground'},
 {type:'surface',x:[[0]],y:[[0]],z:[[0]],showscale:false,opacity:.33,colorscale:col('#4c78a8'),hoverinfo:'skip',name:'equal-path ellipsoid'},
 {type:'scatter3d',mode:'markers+text',x:[T[0]],y:[T[1]],z:[T[2]],text:['WDPN TX'],textposition:'top center',marker:{size:6,color:'red'},name:'TX'},
 {type:'scatter3d',mode:'markers+text',x:[R[0]],y:[R[1]],z:[R[2]],text:['RX'],textposition:'top center',marker:{size:6,color:'blue'},name:'RX'},
 {type:'scatter3d',mode:'lines',x:[T[0],R[0]],y:[T[1],R[1]],z:[T[2],R[2]],line:{color:'gray',width:3,dash:'dash'},name:'baseline'},
 {type:'scatter3d',mode:'lines',x:[0,0],y:[0,0],z:[0,0],line:{color:'green',width:7},name:'meteor path'},
 {type:'cone',x:[0],y:[0],z:[0],u:[1],v:[0],w:[0],sizemode:'absolute',sizeref:14,anchor:'tip',showscale:false,colorscale:col('green'),hoverinfo:'skip'},
 {type:'scatter3d',mode:'lines',x:[0,0],y:[0,0],z:[0,0],line:{color:'rgba(120,120,120,.8)',width:2},name:'RX→P→TX'},
 {type:'scatter3d',mode:'markers',x:[0],y:[0],z:[0],marker:{size:6,color:'black'},name:'reflection point'}];
const dark=matchMedia('(prefers-color-scheme:dark)').matches;
const lay={margin:{l:0,r:0,t:0,b:0},showlegend:false,paper_bgcolor:'rgba(0,0,0,0)',font:{color:dark?'#ddd':'#222'},
 scene:{xaxis:{title:'East km'},yaxis:{title:'North km'},zaxis:{title:'Up km',range:[-10,140]},aspectmode:'data',camera:{eye:{x:1.2,y:-1.6,z:.8}}}};
Plotly.newPlot('g3',tr,lay,{responsive:true});
const lay2={margin:{l:55,r:10,t:22,b:36},title:{text:'Doppler along the trail (the meteor moves →)',font:{size:12}},xaxis:{title:'distance along trail from reflection point P, km'},yaxis:{title:'f_D, Hz'},
 paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:dark?'#ddd':'#222'},showlegend:false,
 shapes:[{type:'rect',xref:'paper',x0:0,x1:1,yref:'y',y0:-100,y1:100,fillcolor:'rgba(26,127,55,.15)',line:{width:0}},{type:'line',x0:0,x1:0,yref:'paper',y0:0,y1:1,line:{dash:'dot',color:'gray'}}]};
Plotly.newPlot('g2',[{x:[0],y:[0],mode:'lines',line:{color:'#d62728'}}],lay2,{responsive:true});
const $=id=>document.getElementById(id);
const ids=['x','y','h','az','d','v'],unit={x:' km',y:' km',h:' km',az:'°',d:'°',v:' km/s'};
function update(){
  const x=+$('x').value,y=+$('y').value,h=+$('h').value,az=+$('az').value,d=+$('d').value,vk=+$('v').value;
  ids.forEach(i=>$('v'+i).textContent=$(i).value+unit[i]);
  const P=place(x,y,h),v=vel(P,az,d),f=fD(P,v,vk),E=ellipsoid(P);
  const ok=Math.abs(f)<=100,L=60;
  const a0=sub(P,sc(v,L)),a1=add(P,sc(v,L));
  Plotly.restyle('g3',{x:[E.X],y:[E.Y],z:[E.Zz]},[1]);
  const c=ok?'#1a7f37':'#d62728';
  Plotly.restyle('g3',{x:[[a0[0],a1[0]]],y:[[a0[1],a1[1]]],z:[[a0[2],a1[2]]],'line.color':c},[5]);
  Plotly.restyle('g3',{x:[[a1[0]]],y:[[a1[1]]],z:[[a1[2]]],u:[[v[0]]],v:[[v[1]]],w:[[v[2]]],colorscale:[col(c)]},[6]);
  Plotly.restyle('g3',{x:[[R[0],P[0],T[0]]],y:[[R[1],P[1],T[1]]],z:[[R[2],P[2],T[2]]]},[7]);
  Plotly.restyle('g3',{x:[[P[0]]],y:[[P[1]]],z:[[P[2]]]},[8]);
  $('fd').textContent=(f>=0?'+':'')+f.toFixed(0)+' Hz';$('fd').className=ok?'ok':'bad';
  const b=bis(P),fr=frame(P);
  $('fdinfo').firstChild.innerHTML=`at reflection point; max possible ±${(vk*1000/K.LAM*nrm(b)).toFixed(0)} Hz at ${vk} km/s.<br>Path length TX→P→RX = ${E.S.toFixed(1)} km; ranges ${nrm(sub(P,R)).toFixed(0)} km (RX), ${nrm(sub(P,T)).toFixed(0)} km (TX).<br>Bisector elevation ${(Math.asin(dot(b,fr.up)/nrm(b))/D2R).toFixed(0)}°.`;
  const xs=[],ys=[];for(let s=-L;s<=L;s+=1){const Q=add(P,sc(v,s));if(nrm(sub(Q,K.C))<K.RE){continue}xs.push(s);ys.push(fD(Q,v,vk))}
  Plotly.react('g2',[{x:xs,y:ys,mode:'lines',line:{color:'#d62728',width:2}}],lay2);
}
ids.forEach(i=>$(i).addEventListener('input',update));
$('snap').onclick=()=>{const x=+$('x').value,y=+$('y').value,h=+$('h').value,az=+$('az').value;
  const P=place(x,y,h),b=bis(P),f=frame(P),hh=dot(b,f.e)*Math.sin(az*D2R)+dot(b,f.n)*Math.cos(az*D2R),bu=dot(b,f.up);
  let d=Math.atan2(hh,bu)/D2R;if(d<-90)d+=180;if(d>90)d-=180;
  if(d>=0&&d<=90){$('d').value=d.toFixed(1);update()}else{$('fdinfo').firstChild.innerHTML='<b>No 0 Hz descent at this heading</b> (it would have to climb: '+d.toFixed(1)+'°). Try another heading.'}};
document.querySelectorAll('button[data-p]').forEach(b=>b.onclick=()=>{$('x').value={q:-52,m:0,t:52}[b.dataset.p];$('y').value=0;update()});
$('ex').onchange=e=>Plotly.relayout('g3',{'scene.aspectmode':e.target.checked?'manual':'data','scene.aspectratio':{x:1,y:1,z:.5}});
update();
</script></body></html>"""

html = PAGE.replace("__PLOTLY__", get_plotlyjs()).replace("__K__", json.dumps(K))
open("meteor_3d_interactive.html", "w", encoding="utf-8").write(html)
print("wrote meteor_3d_interactive.html", round(len(html) / 1e6, 1), "MB")
