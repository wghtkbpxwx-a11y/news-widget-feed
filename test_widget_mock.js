// Runs widget.js against a mocked Scriptable API using the local feed.json (smoke test only).
const fs = require("fs"), vm = require("vm");
const log = [];
class Stk { constructor(){this.k=[]} addText(s){const t={s,font:null};log.push(s);return t} addStack(){return new Stk()} addSpacer(){} centerAlignContent(){} topAlignContent(){} setPadding(){} layoutVertically(){} }
class LW extends Stk { }
const ctx = { console, Date, JSON, String, Array, Error, Promise, Math,
  Color: class{constructor(h){this.h=h}}, Size: class{}, Font: {boldSystemFont:()=>1,semiboldSystemFont:()=>1,systemFont:()=>1},
  ListWidget: LW, config: {runsInWidget:false},
  Request: class{ async loadJSON(){ return JSON.parse(fs.readFileSync("feed.json")) } },
  FileManager:{local:()=>({joinPath:(a,b)=>a+"/"+b,documentsDirectory:()=>"/tmp",writeString:(p,s)=>fs.writeFileSync(p,s),fileExists:p=>fs.existsSync(p),readString:p=>fs.readFileSync(p,"utf8")})},
  Script:{setWidget(){},complete(){console.log("complete")}} };
LW.prototype.presentLarge = async()=>console.log("presentLarge ok");
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("widget.js","utf8"), ctx);
setTimeout(()=>console.log(log.length+" text nodes:\n"+log.join("\n")),300);
