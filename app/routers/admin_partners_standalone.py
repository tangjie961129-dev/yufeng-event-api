"""渠道主管理后台 — 独立静态路由"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/api/admin/channel", tags=["渠道主管理"])

_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>屿风 · 渠道管理后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;background:#1a1a2e;color:#e8e8e8;min-height:100vh;padding:16px}
.container{max-width:960px;margin:0 auto}
.card{background:#16213e;border-radius:16px;padding:24px;margin-bottom:16px;border:1px solid #233554}
h1{font-size:20px;color:#e94560;margin-bottom:16px}
.stat-row{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}
.stat-item{flex:1;min-width:100px;text-align:center;background:rgba(255,255,255,0.03);border-radius:12px;padding:16px}
.stat-num{font-size:24px;font-weight:700}
.s-accent{color:#e94560}.s-blue{color:#4fc3f7}.s-green{color:#64ffda}.s-orange{color:#ffa726}.s-purple{color:#ce93d8}
.stat-label{font-size:11px;color:#8892b0;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:#8892b0;padding:8px;border-bottom:1px solid #233554;font-weight:500}
td{padding:10px 8px;border-bottom:1px solid rgba(255,255,255,0.05)}
.tag{display:inline-block;font-size:11px;padding:2px 8px;border-radius:8px;background:#0f3460;color:#8892b0}
.tag.active{background:#1b4332;color:#64ffda}
.tag.done{background:#1b4332;color:#64ffda}
.tag.pending{background:#3d2e0c;color:#ffd700}
.tab-bar{display:flex;background:#0d1b2a;border-radius:10px;overflow:hidden;margin-bottom:16px}
.tab{flex:1;text-align:center;padding:10px;font-size:13px;cursor:pointer;color:#8892b0}
.tab.active{background:#e94560;color:white}
.hidden{display:none}
.btn-sm{padding:6px 14px;border:none;border-radius:6px;font-size:12px;cursor:pointer;margin-right:4px}
.btn-deal{background:#1b4332;color:#64ffda}
.btn-approve{background:#1b4332;color:#64ffda}
.btn-reject{background:#3d0c11;color:#ff6b6b}
.input-row{display:flex;gap:8px}
.input-row input{flex:1;padding:10px;background:#0d1b2a;color:#e8e8e8;border:1px solid #233554;border-radius:8px;font-size:14px}
.input-row input.small{flex:0 0 80px}
</style>
</head>
<body>
<div class="container" id="app"></div>
<script>
var API="/partner/admin",pwd=localStorage.getItem("pa2")||"";
function esc(s){var d=document.createElement("div");d.textContent=s||"";return d.innerHTML}
function $(v){return Number(v||0).toFixed(2)}
function r(){if(!pwd){L();return;}A();}
function L(){document.getElementById("app").innerHTML='<div class="card" style="max-width:400px;margin:40px auto;text-align:center"><h1>🔐 渠道管理</h1><p style="color:#8892b0;font-size:13px;margin-bottom:20px">屿风渠道主分销后台</p><input type="password" id="pw" placeholder="管理密码" autofocus onkeydown="if(event.keyCode===13)D()"/><br><br><button class="tab active" onclick="D()" style="flex:none;padding:10px 40px;border:none;background:#e94560;color:white;border-radius:8px;font-size:14px;cursor:pointer">登录</button></div>';}
function D(){pwd=document.getElementById("pw").value.trim();if(!pwd)return;fetch(API+"/login?password="+encodeURIComponent(pwd)).then(function(r){if(!r.ok){alert("密码错误");pwd="";L();return;}localStorage.setItem("pa2",pwd);A();});}
function A(){document.getElementById("app").innerHTML='<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px"><h1>📊 渠道管理</h1><button onclick="lo()" style="padding:6px 16px;border:none;border-radius:6px;background:#e94560;color:white;font-size:12px;cursor:pointer">退出</button></div><div class="tab-bar"><div class="tab active" onclick="sw(this,\'p\')">渠道主</div><div class="tab" onclick="sw(this,\'pe\')">待审核</div><div class="tab" onclick="sw(this,\'w\')">提现</div><div class="tab" onclick="sw(this,\'r\')">成交录入</div></div><div id="tp"></div><div id="tpe" class="hidden"></div><div id="tw" class="hidden"></div><div id="tr" class="hidden"></div>';getP();getW();}
function sw(el,t){document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active")});el.classList.add("active");var m={p:"tp",pe:"tpe",w:"tw",r:"tr"};for(var k in m){document.getElementById(m[k]).classList.toggle("hidden",k!==t)}if(t==="r")getR();}
function getP(){fetch(API+"/partners?password="+encodeURIComponent(pwd)).then(function(r){if(!r.ok){lo();return;}return r.json()}).then(function(d){if(!d)return;var t=d.total||{},ps=d.partners||[];var rows=ps.map(function(p){return"<tr><td><strong>"+esc(p.name)+'</strong><br><span class="tag">'+p.partner_id+'</span></td><td>"+p.total_registers+"</td><td>"+p.total_deals+"</td><td>"+$(p.deal_amount)+"</td><td>"+$(p.total_commission)+"</td><td>"+$(p.withdrawable)+'</td><td><span class="tag '+p.status+'">'+p.status+"</span></td></tr>"}).join("");document.getElementById("tp").innerHTML='<div class="card"><div class="stat-row"><div class="stat-item"><div class="stat-num s-accent">'+t.partners+'</div><div class="stat-label">渠道主</div></div><div class="stat-item"><div class="stat-num s-blue">'+t.registers+'</div><div class="stat-label">总填表</div></div><div class="stat-item"><div class="stat-num s-green">'+t.deals+'</div><div class="stat-label">加微</div></div><div class="stat-item"><div class="stat-num s-orange">'+(t.dealt_count||0)+'</div><div class="stat-label">成交数</div></div><div class="stat-item"><div class="stat-num s-purple">'+$(t.deal_amount)+'</div><div class="stat-label">成交金额</div></div><div class="stat-item"><div class="stat-num s-accent">'+$(t.commission)+'</div><div class="stat-label">总佣金</div></div></div></div><div class="card"><table><tr><th>渠道主</th><th>填表</th><th>加微</th><th>成交金额</th><th>佣金</th><th>余额</th><th>状态</th></tr>'+(rows||'<tr><td colspan="7" style="text-align:center;color:#495670">暂无数据</td></tr>')+"</table></div>";setTimeout(getPe,50)}).catch(function(e){document.getElementById("tp").innerHTML='<div class="card"><p>加载失败</p></div>'})}
function getPe(){fetch(API+"/partners?password="+encodeURIComponent(pwd)).then(function(r){return r.json()}).then(function(d){var pe=(d.partners||[]).filter(function(p){return p.status==="pending"||p.status==="rejected"});var rows=pe.map(function(p){return"<tr><td><strong>"+esc(p.name)+'</strong><br><span class="tag">'+p.partner_id+'</span></td><td>"+(p.phone||"-")+"</td><td>"+(p.wechat||"-")+"</td><td>"+p.created_at+'</td><td><span class="tag '+p.status+'">'+p.status+'</span></td><td>'+(p.status==="pending"?'<button class="btn-sm btn-approve" onclick="ap(\''+p.partner_id+'\',\'approve\')">通过</button><button class="btn-sm btn-reject" onclick="ap(\''+p.partner_id+'\',\'reject\')">拒绝</button>':"-")+"</td></tr>"}).join("");document.getElementById("tpe").innerHTML='<div class="card"><table><tr><th>姓名</th><th>手机</th><th>微信</th><th>申请时间</th><th>状态</th><th>操作</th></tr>'+(rows||'<tr><td colspan="6" style="text-align:center;color:#495670">暂无待审核</td></tr>')+"</table></div>"}).catch(function(){})}
function ap(pid,action){if(!confirm("确定"+(action==="approve"?"通过":"拒绝")+"这个渠道主吗？"))return;fetch(API+"/approve_partner?password="+encodeURIComponent(pwd)+"&partner_id="+pid+"&action="+action).then(function(r){if(r.ok){getPe();getP();}})}
function getW(){fetch(API+"/withdraws?password="+encodeURIComponent(pwd)+"&status=all").then(function(r){if(!r.ok)return;return r.json()}).then(function(d){var rows=(d.list||[]).map(function(w){return"<tr><td>"+esc(w.partner_name)+'<br><span class="tag">'+w.partner_id+'</span></td><td>'+$(w.amount)+"</td><td>"+(w.method||"")+'</td><td><span class="tag '+w.status+'">'+w.status+'</span></td><td>'+w.created_at+"</td><td>"+(w.status==="pending"?'<button class="btn-sm btn-approve" onclick="aw('+w.id+',\'done\')">打款</button><button class="btn-sm btn-reject" onclick="aw('+w.id+',\'reject\')">拒绝</button>':"-")+"</td></tr>"}).join("");document.getElementById("tw").innerHTML='<div class="card"><table><tr><th>渠道主</th><th>金额</th><th>方式</th><th>状态</th><th>申请时间</th><th>操作</th></tr>'+(rows||'<tr><td colspan="6" style="text-align:center;color:#495670">暂无提现</td></tr>')+"</table></div>"}).catch(function(){})}
function aw(id,action){if(!confirm("确定"+(action==="done"?"打款":"拒绝")+"这笔提现吗？"))return;fetch(API+"/approve_withdraw?password="+encodeURIComponent(pwd)+"&withdraw_id="+id+"&action="+action).then(function(r){if(r.ok){getW();getP();}})}
function getR(){document.getElementById("tr").innerHTML='<div class="card"><h1>📝 记录成交</h1><p style="color:#8892b0;font-size:13px;margin-bottom:12px">客户在企微转账后，在这里录入成交金额和分佣</p><div class="input-row"><input class="small" id="rid" type="number" placeholder="记录ID" /><input id="amt" type="number" step="0.01" placeholder="成交金额(元)" /><input id="fee" type="number" step="0.01" placeholder="分佣(元)" /><button class="btn-sm btn-deal" onclick="sd()">记录成交</button></div></div><div class="card"><h1>📊 渠道主成交概览</h1>';getRO();}
function getRO(){fetch(API+"/partners?password="+encodeURIComponent(pwd)).then(function(r){return r.json()}).then(function(d){var ps=d.partners||[];var h="<table><tr><th>渠道主</th><th>填表</th><th>加微</th><th>成交金额</th><th>佣金</th></tr>";ps.forEach(function(p){h+="<tr><td><strong>"+esc(p.name)+'</strong><br><span class="tag">'+p.partner_id+'</span></td><td>'+p.total_registers+"</td><td>"+p.total_deals+"</td><td>"+$(p.deal_amount)+"</td><td>"+$(p.total_commission)+"</td></tr>"});h+="</table><p style='color:#495670;font-size:12px;margin-top:12px'>💡 记录ID可以在客户填表成功后的提示中找到，或让我帮你查</p>";document.getElementById("tr").innerHTML+=h+"</div>"}).catch(function(){})}
function sd(){var rid=document.getElementById("rid").value.trim();var amt=parseFloat(document.getElementById("amt").value);var fee=parseFloat(document.getElementById("fee").value)||0;if(!rid||isNaN(amt)||amt<=0){alert("请填写记录ID和成交金额");return;}fetch(API+"/record_deal?password="+encodeURIComponent(pwd)+"&register_id="+rid+"&deal_amount="+amt+"&deal_fee="+fee).then(function(r){if(!r.ok){r.text().then(function(t){alert("失败: "+t)});return;}r.json().then(function(d){alert("✅ 成交已记录！"+d.customer+" 成交¥"+d.deal_amount+" 分佣¥"+d.deal_fee);document.getElementById("rid").value="";document.getElementById("amt").value="";document.getElementById("fee").value="";getP();getR()})}).catch(function(){alert("网络错误")})}
function lo(){pwd="";localStorage.removeItem("pa2");L()}
r();
</script>
</body>
</html>"""

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def page():
    return HTMLResponse(content=_HTML)
