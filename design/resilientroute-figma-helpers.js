
const ids=[];const vs=await figma.variables.getLocalVariablesAsync();const V=Object.fromEntries(vs.map(v=>[v.name,v]));const styles=Object.fromEntries((await figma.getLocalTextStylesAsync()).map(s=>[s.name,s]));
await Promise.all([{family:"DM Sans",style:"Regular"},{family:"DM Sans",style:"Medium"},{family:"Caveat",style:"Regular"},{family:"Noto Sans TC",style:"Regular"}].map(f=>figma.loadFontAsync(f)));
function paint(name){return figma.variables.setBoundVariableForPaint({type:"SOLID",color:{r:0,g:0,b:0}},"color",V[name]);}
function bind(n,field,key){n.setBoundVariable(field,V[key]);}
function box(parent,name,w,h,dir="VERTICAL",bg=null,pad=0,gap=16,radius=0){const n=figma.createAutoLayout(dir);n.name=name;parent.appendChild(n);n.resize(w,h||40);n.layoutSizingHorizontal="FIXED";n.layoutSizingVertical=h?"FIXED":"HUG";n.fills=bg?[paint(bg)]:[];for(const side of ["Top","Bottom","Left","Right"])bind(n,"padding"+side,"space/"+pad);bind(n,"itemSpacing","space/"+gap);for(const corner of ["topLeftRadius","topRightRadius","bottomLeftRadius","bottomRightRadius"])bind(n,corner,"radius/"+radius);n.clipsContent=false;ids.push(n.id);return n;}
async function txt(parent,name,value,style="Body",color="text/primary",width=null){const n=figma.createText();parent.appendChild(n);n.name=name;await n.setTextStyleIdAsync(styles["RR/"+style].id);n.fills=[paint(color)];n.textAutoResize=width?"HEIGHT":"WIDTH_AND_HEIGHT";if(width)n.resize(width,30);n.characters=value;n.textAutoResize=width?"HEIGHT":"WIDTH_AND_HEIGHT";ids.push(n.id);return n;}
function rect(parent,name,w,h,color,r=0){const n=figma.createRectangle();parent.appendChild(n);n.name=name;n.resize(w,h);n.fills=[paint(color)];bind(n,"cornerRadius","radius/"+r);ids.push(n.id);return n;}
function allIds(root){return [root.id,...root.findAll(()=>true).map(n=>n.id)];}
async function instance(parent,comp,label=null){const n=(await figma.getNodeByIdAsync(comp)).createInstance();parent.appendChild(n);if(label){const key=Object.keys(n.componentProperties).find(k=>k.startsWith("Label#"));if(key)n.setProperties({[key]:label});}ids.push(...allIds(n));return n;}

