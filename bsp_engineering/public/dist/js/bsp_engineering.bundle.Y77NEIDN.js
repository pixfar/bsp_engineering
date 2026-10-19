(()=>{var q=Object.defineProperty,N=Object.defineProperties;var j=Object.getOwnPropertyDescriptors;var I=Object.getOwnPropertySymbols;var z=Object.prototype.hasOwnProperty,W=Object.prototype.propertyIsEnumerable;var P=(e,r,t)=>r in e?q(e,r,{enumerable:!0,configurable:!0,writable:!0,value:t}):e[r]=t,b=(e,r)=>{for(var t in r||(r={}))z.call(r,t)&&P(e,t,r[t]);if(I)for(var t of I(r))W.call(r,t)&&P(e,t,r[t]);return e},g=(e,r)=>N(e,j(r));console.log("BSP: bsp_column_picker.js loaded");frappe.provide("frappe.views");function X(e){if(!e||!e.columns||!e.columns.length){frappe.msgprint(__("Please run the report first."));return}let r=new frappe.ui.Dialog({title:__("Pick Columns"),fields:[{label:__("Select columns to show"),fieldname:"columns",fieldtype:"MultiCheck",options:e.columns.map(t=>({label:t.label||t.name||t.fieldname||t.id,value:t.fieldname||t.id,checked:!t.hidden}))}],primary_action_label:__("Apply"),primary_action:t=>{let n=t.columns||[];e.columns.forEach(i=>{let s=i.fieldname||i.id;i.hidden=!n.includes(s)}),e._bsp_col_prefs={docname:e._bsp_col_prefs&&e._bsp_col_prefs.docname,visible_columns:n},e.render_datatable(),frappe.call({method:"bsp_engineering.api.report_prefs.save_column_visibility",args:{report_name:e.report_name,visible_columns:JSON.stringify(n)},callback:function(i){i.message&&(e._bsp_col_prefs={docname:i.message,visible_columns:n})}}),r.hide()}});r.set_secondary_action_label(__("Reset to Default")),r.set_secondary_action(()=>{let t=e._bsp_col_prefs;t&&t.docname?frappe.db.delete_doc("Report Column Visibility",t.docname).then(()=>{e._bsp_col_prefs=null,e.columns.forEach(n=>{n.hidden=n._bsp_original_hidden||!1}),e.render_datatable(),r.hide()}):(e.columns.forEach(n=>{n.hidden=n._bsp_original_hidden||!1}),e.render_datatable(),r.hide())}),r.show()}function R(e,r){!r||!e.columns||e.columns.forEach(t=>{t._bsp_original_hidden===void 0&&(t._bsp_original_hidden=t.hidden||!1);let n=t.fieldname||t.id;t.hidden=!r.includes(n)})}function x(e){if(!e||!e.page)return;let r=e.page;r.wrapper.find(".bsp-pick-columns-btn").length||r.add_button(__("Pick Columns"),()=>{X(e)}).addClass("bsp-pick-columns-btn")}var V=["posting_date","date","transaction_date","posting_datetime"];function J(e){let r=(e.columns||[]).filter(n=>!n.hidden),t=n=>["Date","Datetime"].includes(n.fieldtype);return r.find(n=>t(n)&&V.includes(n.fieldname))||r.find(n=>t(n)&&["Date","Posting Date"].includes(n.label))}function Y(e){let r=e.datatable;if(!r||!r.datamanager||e.tree_report||e.report_settings&&e.report_settings.bsp_default_date_sort===!1)return;let t=J(e);if(!t)return;let n=r.datamanager.getColumns().find(a=>a.id===t.fieldname||a.id===t.id);if(!n||n.sortOrder&&n.sortOrder!=="none")return;let i=(e.data||[]).map(a=>a&&a[t.fieldname]).filter(Boolean).map(String);i.length<2||i.every((a,_)=>_===0||i[_-1]>=a)||(r.datamanager.rowViewOrder.reverse(),r.sortColumn(n.colIndex,"desc"))}var U=60,K=240,Z=200,ee=["Data","Small Text","Text","Long Text","Text Editor","Dynamic Link"],D=22,te=24,re=100,v=null;function ne(e){return!e||e.tree_report?!1:!(e.report_settings&&e.report_settings.bsp_fit_columns===!1)}function C(e,r){v=v||document.createElement("canvas");let t=v.getContext("2d");return t.font=r,t.measureText(e).width}function ie(e,r,t){if(e==null||e==="")return"";let n=e;try{n=frappe.format(e,r,{only_value:!0},t)}catch(i){n=e}return String(n).replace(/<[^>]*>/g,"").replace(/&nbsp;/g," ").trim()}function se(){if(document.getElementById("bsp-fit-report-style"))return;let e=document.createElement("style");e.id="bsp-fit-report-style",e.textContent=`
        .bsp-fit-report .dt-header .dt-row-header {
            height: auto !important;
        }
        .bsp-fit-report .dt-row-header .dt-cell--header,
        .bsp-fit-report .dt-row-header .dt-cell--header .dt-cell__content {
            height: auto !important;
            white-space: normal !important;
            text-overflow: clip !important;
            line-height: 1.25;
        }
        .bsp-fit-report .dt-row-header .dt-cell--header .dt-cell__content {
            word-break: normal;
            overflow-wrap: normal;
            padding-left: 6px;
            padding-right: 6px;
        }
    `,document.head.appendChild(e)}function ae(e){let r=[e.$report,e.$report&&e.$report.parent(),$(e.page&&e.page.main)];for(let t of r){let n=t&&t.length?t.width():0;if(n)return n}return 0}function oe(e){if(!ne(e))return;let r=(e.columns||[]).filter(o=>!o.hidden);if(!r.length)return;let t=ae(e);if(!t)return;se(),e.$report.addClass("bsp-fit-report"),le(e);let n=getComputedStyle(document.body),i=`13px ${n.fontFamily}`,s=`600 13px ${n.fontFamily}`,a=(e.data||[]).slice(0,re),_=r.map(o=>{let p=String(o.name||o.label||"").split(/\s+/),l=Math.max(...p.map(c=>C(c,s)))+te-D;for(let c of a){if(!c)continue;let k=ie(c[o.fieldname],o,c);k&&(l=Math.max(l,C(k,i)))}let Q=ee.includes(o.fieldtype)||/(^|_)(name|description|remarks)$/.test(o.fieldname||"")?Z:K;return Math.min(Q,Math.max(U,Math.ceil(l+D)))}),d=String((e.data||[]).length).length*9+30,u=t-d-20,m=_.reduce((o,p)=>o+p,0),h=Math.max(0,u-m)/r.length;r.forEach((o,p)=>{o.width=Math.floor(_[p]+h)})}function le(e){if(e._bsp_fit_resize_bound)return;e._bsp_fit_resize_bound=!0;let r=null;$(window).on("resize",()=>{clearTimeout(r),r=setTimeout(()=>{frappe.query_report!==e||!e.datatable||!frappe.get_route||frappe.get_route()[0]!=="query-report"||e.render_datatable()},300)})}var pe=setInterval(()=>{if(!frappe.views||!frappe.views.QueryReport||frappe.views.QueryReport.prototype._bsp_patched)return;clearInterval(pe),frappe.views.QueryReport.prototype._bsp_patched=!0;let e=frappe.views.QueryReport.prototype.render_datatable;frappe.views.QueryReport.prototype.render_datatable=function(){this._bsp_col_prefs&&this._bsp_col_prefs.visible_columns&&R(this,this._bsp_col_prefs.visible_columns),oe(this);let n=e.call(this);return Y(this),n};let r=frappe.views.QueryReport.prototype.setup_page_head;frappe.views.QueryReport.prototype.setup_page_head=function(){r.call(this),x(this)};let t=frappe.views.QueryReport.prototype.refresh;frappe.views.QueryReport.prototype.refresh=function(){let n=t.apply(this,arguments);return this._bsp_load_and_apply_prefs(),n},frappe.views.QueryReport.prototype._bsp_load_and_apply_prefs=function(){let n=this;!n.report_name||n._bsp_prefs_loaded_for!==n.report_name&&(n._bsp_prefs_loaded_for=n.report_name,frappe.db.get_list("Report Column Visibility",{filters:{user:frappe.session.user,report_name:n.report_name},fields:["name","visible_columns"],order_by:"creation desc",limit:1}).then(i=>{if(i&&i.length){let s=JSON.parse(i[0].visible_columns);n._bsp_col_prefs={docname:i[0].name,visible_columns:s},n.columns&&n.columns.length&&(R(n,s),n.datatable&&n.render_datatable())}else n._bsp_col_prefs=null}))},frappe.query_report&&frappe.query_report.report_name&&(frappe.query_report._bsp_load_and_apply_prefs(),x(frappe.query_report))},100);setInterval(()=>{frappe.get_route&&frappe.get_route()[0]==="query-report"&&frappe.query_report&&x(frappe.query_report)},1e3);(function(){let r=frappe.provide("frappe.form.link_formatters"),t=r.Item;Object.defineProperty(r,"Item",{configurable:!0,enumerable:!0,get(){if(!!t)return function(n,i,s){return n||t.call(this,n,i,s)}},set(n){t=n}})})();frappe.provide("bsp_engineering.item_code");bsp_engineering.item_code.fill=async function(e,r){if(!(!e||e.item_code||e.variant_of))try{let{message:t}=await frappe.call({method:"bsp_engineering.doc_events.item.auto_item_code.get_next_item_code"});if(!t||e.item_code)return;e.__bsp_auto_code=t,await r(t)}catch(t){console.error("Could not fetch next Item Code",t)}};var L,O;((O=(L=frappe.ui)==null?void 0:L.form)==null?void 0:O.QuickEntryForm)&&!frappe.ui.form.ItemQuickEntryForm&&(frappe.ui.form.ItemQuickEntryForm=class extends frappe.ui.form.QuickEntryForm{render_dialog(){super.render_dialog(),this.dialog.fields_dict.item_code&&bsp_engineering.item_code.fill(this.dialog.doc,r=>this.dialog.set_value("item_code",r))}});var B="Item";var _e="\u09E6\u09E7\u09E8\u09E9\u09EA\u09EB\u09EC\u09ED\u09EE\u09EF",H=e=>String(e!=null?e:"").replace(/[০-৯]/g,r=>_e.indexOf(r)).toLowerCase();function de(e,r){let t=H(e).split(/\s+/).filter(Boolean);if(!t.length)return!0;let n=r.map(H);return t.every(i=>n.some(s=>s.includes(i)))}var A=e=>e.scrollHeight-e.scrollTop-e.clientHeight<40,fe={"frappe.desk.search.search_link":(e,r)=>g(b({},e),{start:r.start,page_length:r.page_length}),"erpnext.controllers.queries.item_query":(e,r)=>g(b({},e),{start:r.start,page_len:r.page_length})},y=null,ce=frappe.call;frappe.call=function(e,...r){let t=y&&e&&typeof e=="object"&&fe[e.method];return t&&(e=g(b({},e),{args:t(e.args||{},y)})),ce.call(this,e,...r)};function ue(e,r){y=e;try{return r()}finally{y=null}}var S=frappe.ui.form.ControlLink.prototype,me=S.setup_awesomeplete;S.setup_awesomeplete=function(){me.call(this),this._bsp_exhausted={},$(this.awesomplete.ul).on("scroll",()=>this.bsp_load_more_items())};S.bsp_load_more_items=function(){var u,m;let e=this.get_options(),r=this.awesomplete.ul;if(e!==B||this._bsp_loading||!A(r))return;let t=this.$input.val(),n=this.$input.cache[e],i=n&&n[t];if(!i||this._bsp_exhausted[t])return;let s=i.filter(f=>!f.action),a=i.filter(f=>f.action),_=cint((u=frappe.boot.sysdefaults)==null?void 0:u.link_field_results_limit)||10;if(s.length<_)return;let d={txt:t,doctype:e,ignore_user_permissions:(m=this.df)==null?void 0:m.ignore_user_permissions,reference_doctype:this.get_reference_doctype()||"",page_length:20,start:s.length};this.set_custom_query(d),this._bsp_loading=!0,frappe.call({type:"POST",method:"frappe.desk.search.search_link",no_spinner:!0,args:d}).then(f=>{let h=f.message||[];h.length<20&&(this._bsp_exhausted[t]=!0);let o=new Set(s.map(l=>l.value)),p=h.filter(l=>!o.has(l.value));if(!p.length||(p.forEach(l=>frappe.utils.add_link_title(e,l.value,l.label)),n[t]=s.concat(p,a),this.$input.val()!==t))return;let E=r.scrollTop;this.awesomplete.maxItems=Math.max(this.awesomplete.maxItems,n[t].length),this.awesomplete.list=n[t],r.scrollTop=E}).always(()=>{this._bsp_loading=!1})};var w=frappe.ui.form.ControlMultiSelectList.prototype,he=w.make_input,be=e=>(e||[]).map(r=>typeof r=="string"?{label:r,value:r}:(r.label||(r.label=r.value),r));w.make_input=function(){he.call(this),this.$list_wrapper.off("input","input"),this.$list_wrapper.on("input","input",frappe.utils.debounce(()=>{this._bsp_exhausted=!1,this.set_options().then(()=>this.bsp_render_options())},300)),this.$list_wrapper.on("show.bs.dropdown",()=>{this._bsp_exhausted=!1}),this.$list_wrapper.find(".selectable-items").on("scroll",e=>this.bsp_load_more_options(e.currentTarget))};w.bsp_render_options=function(){let e=this.$filter_input.val(),r=this._options.filter(t=>this.values.includes(t.value)||de(e,[t.label,t.value,t.description]));this.set_selectable_items(this._selected_values.concat(r).uniqBy(t=>t.value))};w.bsp_load_more_options=function(e){if(this.df.options!==B||!this.df.get_data||this._bsp_loading||this._bsp_exhausted||!A(e))return;let r=this.$filter_input.val();this._bsp_loading=!0,Promise.resolve(ue({start:this._options.length,page_length:20},()=>this.df.get_data(r))).then(t=>{t=be(t);let n=new Set(this._options.map(a=>a.value)),i=t.filter(a=>!n.has(a.value));if((t.length<20||!i.length)&&(this._bsp_exhausted=!0),!i.length||this.$filter_input.val()!==r)return;this._options=this._options.concat(i);let s=e.scrollTop;this.bsp_render_options(),e.scrollTop=s}).finally(()=>{this._bsp_loading=!1})};frappe.provide("bsp_engineering.report_print");var F="{{ base_url }}/assets/bsp_engineering/fonts/hind_siliguri",M=4,ge=`
	@font-face {
		font-family: "Hind Siliguri";
		font-weight: normal;
		src: url("${F}/HindSiliguri-Regular.ttf") format("truetype");
	}
	@font-face {
		font-family: "Hind Siliguri";
		font-weight: bold;
		src: url("${F}/HindSiliguri-Bold.ttf") format("truetype");
	}
	.bsp-report-print,
	.bsp-report-print .print-format,
	.bsp-report-print table {
		font-family: "Hind Siliguri", sans-serif !important;
		-webkit-print-color-adjust: exact;
		print-color-adjust: exact;
	}
	.bsp-report-head {
		background-color: #1f3a5f;
		color: #ffffff;
		text-align: center;
		padding: 10px 12px 8px;
		margin: 0 0 10px 0;
		text-transform: uppercase;
	}
	/* Set on the lines themselves: the site's print style colours text
	   directly, which beats colour inherited from the banner. */
	.bsp-report-print .bsp-report-head,
	.bsp-report-print .bsp-report-head .bsp-report-company,
	.bsp-report-print .bsp-report-head .bsp-report-title {
		color: #ffffff !important;
	}
	.bsp-report-company {
		font-size: 18pt;
		font-weight: bold;
		line-height: 1.2;
	}
	.bsp-report-title {
		font-size: 12pt;
		font-weight: bold;
		line-height: 1.3;
		margin-top: 2px;
	}
	.bsp-report-print table.bsp-report-filters {
		margin: 0 auto 12px auto;
		border-collapse: collapse;
		width: auto;
	}
	.bsp-report-filters td {
		border: 1px solid #c8d2de;
		padding: 4px 10px !important;
		font-size: 8pt;
		white-space: nowrap;
	}
	.bsp-report-filters td.bsp-filter-label {
		background-color: #e6ecf3;
		color: #4a5b70;
		font-weight: bold;
		text-transform: uppercase;
	}
	.bsp-report-filters td.bsp-filter-value {
		color: #1b2733;
		font-weight: bold;
	}
	.bsp-report-print table.table-bordered > thead > tr > th {
		background-color: #1f3a5f !important;
		color: #ffffff !important;
		text-align: center !important;
		vertical-align: middle !important;
		font-weight: bold;
		padding: 5px 4px !important;
		line-height: 1.2;
		border: 1px solid #34537a !important;
	}
	.bsp-report-print table.table-bordered > tbody > tr {
		height: auto !important;
	}
	.bsp-report-print table.table-bordered > tbody > tr > td {
		padding: 3px 5px !important;
		line-height: 1.25;
		vertical-align: middle;
		border-color: #c8d2de !important;
	}
	.bsp-report-print table.table-bordered > tbody > tr:nth-child(even) > td {
		background-color: #f4f7fb;
	}
	.bsp-report-print table.table-bordered > tbody > tr.bsp-total-row > td {
		background-color: #dce6f2;
		font-weight: bold;
	}
`;function G(e){return $("<div>").html(String(e)).text().trim()}function T(e,r){if(e==null||e==="")return"";if(Array.isArray(e)){let t=r&&r.fieldtype==="DateRange",n={fieldtype:t?"Date":"Data"};return e.map(i=>T(i,n)).filter(Boolean).join(t?" - ":", ")}return r&&r.fieldtype==="Check"?cint(e)?__("Yes"):"":G(r?frappe.format(e,r,{only_value:!0,inline:!0}):e)}function ye(e){let r=(e.report&&e.report.filters||[]).filter(t=>t&&t.df);return r.length?r.filter(t=>!t.df.hidden&&t.df.fieldname!=="company").map(t=>({label:__(t.df.label||t.df.fieldname),value:T(t.get_value(),t.df)})).filter(t=>t.value):Object.entries(e.filters||{}).filter(([t])=>t!=="company").map(([t,n])=>({label:__(frappe.unscrub(t)),value:T(n)})).filter(t=>t.value)}function we(e){return e.filters&&e.filters.company||frappe.defaults.get_user_default("Company")||frappe.boot.sysdefaults&&frappe.boot.sysdefaults.company||""}bsp_engineering.report_print.header=function(e){e=e||{};let r=frappe.utils.escape_html,t=we(e),n=`<div class="bsp-report-head">
		${t?`<div class="bsp-report-company">${r(t)}</div>`:""}
		${e.title?`<div class="bsp-report-title">${r(__(e.title))}</div>`:""}
	</div>`,i=ye(e);if(i.length){let s="";for(let a=0;a<i.length;a+=M)s+=`<tr>${i.slice(a,a+M).map(d=>`<td class="bsp-filter-label">${r(d.label)}</td><td class="bsp-filter-value">${r(d.value)}</td>`).join("")}</tr>`;n+=`<table class="bsp-report-filters">${s}</table>`}return n};(function(){let r=frappe.templates||{};r.print_template&&!r.print_template.includes("bsp-report-print")&&(r.print_template=r.print_template.replace("</head>",`<style>${ge}</style></head>`).replace('class="print-format-gutter"','class="print-format-gutter bsp-report-print"'));let t=r.print_grid;if(t&&!t.includes("bsp_engineering.report_print")){let n=t.indexOf("<table"),i=t.indexOf("<!-- title -->")!==-1&&n!==-1?`{{ bsp_engineering.report_print.header(obj) }}
`+t.slice(n):t;i=i.replace('<tr style="height: 30px">','<tr style="height: 30px" {% if (row.is_total_row) { %} class="bsp-total-row" {% } %}>'),r.print_grid=i}delete frappe.template.compiled.print_template,delete frappe.template.compiled.print_grid})();})();
//# sourceMappingURL=bsp_engineering.bundle.Y77NEIDN.js.map
