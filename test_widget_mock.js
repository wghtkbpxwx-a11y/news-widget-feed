// Runs widget.js against a tolerant mocked Scriptable API using a local feed (smoke test only).
// usage: node test_widget_mock.js [feed.json] [large|medium|small]
const fs = require("fs"), vm = require("vm");
const feedPath = process.argv[2] || "feed.json", family = process.argv[3] || "large";
const log = [];
const mk = () => new Proxy(function(){}, {
  get(t, p) {
    if (p === "addText") return s => { log.push(s); return mk(); };
    if (/^(addStack|addImage|addSpacer|addDate)$/.test(p)) return () => mk();
    if (p === "image") return {};
    if (p === Symbol.toPrimitive) return () => "";
    return t[p] !== undefined ? t[p] : (/^(set|center|top|layout|present)/.test(p) ? () => mk() : undefined);
  },
  set(t, p, v) { t[p] = v; return true; }
});
const ctx = { console, Date, JSON, String, Array, Error, Promise, Math, Set, Intl, Object,
  Color: class{constructor(h,a){this.h=h}}, Size: class{}, Point: class{}, Font: {boldSystemFont:()=>1,semiboldSystemFont:()=>1,systemFont:()=>1},
  LinearGradient: class{}, SFSymbol: {named: () => ({image: {}})},
  ListWidget: class { constructor(){ return mk(); } }, config: {runsInWidget:true, widgetFamily: family},
  Request: class{ async loadJSON(){ return JSON.parse(fs.readFileSync(feedPath)) } },
  FileManager:{local:()=>({joinPath:(a,b)=>a+"/"+b,documentsDirectory:()=>"/tmp",writeString:(p,s)=>fs.writeFileSync(p,s),fileExists:p=>fs.existsSync(p),readString:p=>fs.readFileSync(p,"utf8")})},
  Script:{setWidget(){console.log("setWidget ok")},complete(){console.log("complete")}} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("widget.js","utf8"), ctx);
setTimeout(()=>console.log(family + ": " + log.length+" text nodes:\n"+log.join("\n")),300);
