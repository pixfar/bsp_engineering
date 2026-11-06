frappe.provide("bsp_engineering.user_permission");

const DOC_RIGHTS = [
	["view", "read", __("View")],
	["create", "create", __("Create")],
	["update", "write", __("Update")],
	["delete", "delete", __("Delete")],
];

let _mute = false;
let _tab = "places";
let _place = "Company";
let _loaded_role = "";
let _req = 0;

bsp_engineering.user_permission.open = function (user, listview) {
	if (!frappe.user.has_role("System Manager")) {
		frappe.msgprint(__("Only a System Manager can manage permissions."));
		return;
	}
	_ensure_style();

	const dialog = new frappe.ui.Dialog({
		title: __("Manage Permissions"),
		size: "extra-large",
		fields: [
			{
				fieldname: "user",
				fieldtype: "Link",
				options: "User",
				label: __("Person"),
				reqd: 1,
				default: user || "",
				onchange() {
					if (_mute) {
						return;
					}
					_load(dialog, listview, "");
				},
			},
			{
				fieldname: "role",
				fieldtype: "Select",
				label: __("Job"),
				options: "",
				onchange() {
					if (_mute) {
						return;
					}
					const next = dialog.get_value("role");
					if (!next || next === _loaded_role) {
						return;
					}
					_load(dialog, listview, next);
				},
			},
			{
				fieldname: "matrix",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Done"),
		primary_action() {
			dialog.hide();
		},
	});

	_tab = "places";
	_place = "Company";
	dialog.show();
	dialog.get_field("role").$wrapper.hide();
	dialog.$wrapper.find(".modal-dialog").addClass("bsp-perm-dialog");
	if (user) {
		dialog.set_value("user", user);
	} else {
		_empty(dialog);
	}
};

function _empty(dialog) {
	dialog.set_title(__("Manage Permissions"));
	dialog.get_field("matrix").$wrapper.html(
		`<div class="bsp-perm-empty text-muted">${__("Choose a person.")}</div>`,
	);
}

function _load(dialog, listview, role) {
	const user = dialog.get_value("user");
	if (!user) {
		_empty(dialog);
		return;
	}
	const wrapper = dialog.get_field("matrix").$wrapper;
	const req = ++_req;
	wrapper.html(`<div class="bsp-perm-empty text-muted">${__("Loading...")}</div>`);
	frappe.call({
		method: "bsp_engineering.api.user_permission.get_manage_permissions",
		args: { user, role: role || "" },
		callback(r) {
			if (req !== _req || dialog.get_value("user") !== user) {
				return;
			}
			if (!r.message) {
				_fail(wrapper, __("Could not load permissions."));
				return;
			}
			const data = r.message;
			const field = dialog.get_field("role");
			_loaded_role = data.role || "";
			_mute = true;
			field.df.options = (data.roles || []).join("\n");
			field.refresh();
			if (data.role && dialog.get_value("role") !== data.role) {
				dialog.set_value("role", data.role);
			}
			_mute = false;
			_render(dialog, data, listview);
		},
		error(err) {
			if (req !== _req) {
				return;
			}
			const message =
				(err && (err.message || (err._server_messages && err._server_messages[0]))) ||
				__("Could not load permissions.");
			_fail(wrapper, message);
		},
	});
}

function _fail(wrapper, message) {
	wrapper.html(`<div class="bsp-perm-empty text-danger">${frappe.utils.escape_html(String(message))}</div>`);
}

function _render(dialog, data, listview) {
	dialog.set_title(__("Manage Permissions — {0}", [data.full_name || data.user]));
	const wrapper = dialog.get_field("matrix").$wrapper;
	const scroll = wrapper.find(".bsp-perm-scroll").scrollTop() || 0;
	wrapper.html(_screen(data));
	wrapper.find(".bsp-perm-scroll").scrollTop(scroll);
	wrapper.off("change.bspperm").on("change.bspperm", ".bsp-perm-table input", (event) => {
		_on_toggle(dialog, data, event.target, listview);
	});
	wrapper.find(".bsp-perm-tab-btn").on("click", function () {
		_tab = this.dataset.tab;
		_show_tab(dialog, _tab);
	});
	wrapper.find(".bsp-place-tab").on("click", function () {
		_place = this.dataset.place;
		_show_place(wrapper, _place);
	});
	_show_tab(dialog, _tab);
	_show_place(wrapper, _place);
}

function _show_place(wrapper, place) {
	wrapper.find(".bsp-place-tab").removeClass("active");
	wrapper.find(`.bsp-place-tab[data-place="${place}"]`).addClass("active");
	wrapper.find(".bsp-place-panel").attr("hidden", true);
	wrapper.find(`.bsp-place-panel[data-place="${place}"]`).removeAttr("hidden");
}

function _show_tab(dialog, tab) {
	const wrapper = dialog.get_field("matrix").$wrapper;
	wrapper.find(".bsp-perm-tab-btn").removeClass("active");
	wrapper.find(`.bsp-perm-tab-btn[data-tab="${tab}"]`).addClass("active");
	wrapper.find(".bsp-perm-panel").attr("hidden", true);
	wrapper.find(`.bsp-perm-panel[data-panel="${tab}"]`).removeAttr("hidden");
	const role_field = dialog.get_field("role");
	if (role_field) {
		role_field.$wrapper.toggle(tab === "roles");
	}
}

function _screen(data) {
	return `
		<div class="bsp-perm-tabs">
			<button type="button" class="bsp-perm-tab-btn" data-tab="places">${__("Places")}</button>
			<button type="button" class="bsp-perm-tab-btn" data-tab="roles">${__("Role Permissions Manager")}</button>
		</div>
		<div class="bsp-perm-panel" data-panel="places">
			${_place_summary(data)}
			${_place_table(data.places || [])}
		</div>
		<div class="bsp-perm-panel" data-panel="roles" hidden>
			<p class="bsp-perm-note">${__(
				"These ticks are for the job above. Everyone with that job gets them.",
			)}</p>
			${_doc_summary(data)}
			${_doc_table(data.documents || [])}
		</div>`;
}

function _place_summary(data) {
	const places = [];
	(data.places || []).forEach((group) => {
		(group.rows || []).forEach((row) => {
			if (row.allowed) {
				places.push(`${frappe.utils.escape_html(group.label)}: ${frappe.utils.escape_html(row.label || row.value)}`);
			}
		});
	});
	const body = places.length
		? `<ul>${places.map((line) => `<li>${line}</li>`).join("")}</ul>`
		: `<p class="bsp-perm-note">${__("No place limit. This person can see every warehouse and area.")}</p>`;
	return `
		<div class="bsp-perm-now">
			<div class="bsp-perm-now-title">${__("Already allowed")}</div>
			${body}
		</div>`;
}

function _doc_summary(data) {
	const docs = [];
	(data.documents || []).forEach((group) => {
		(group.rows || []).forEach((row) => {
			const words = _right_words(row.perms);
			if (words) {
				docs.push(`${frappe.utils.escape_html(row.label)} — ${frappe.utils.escape_html(words)}`);
			}
		});
	});
	const body = docs.length
		? `<ul>${docs.map((line) => `<li>${line}</li>`).join("")}</ul>`
		: `<p class="bsp-perm-note">${__("This job has none of these documents yet.")}</p>`;
	return `
		<div class="bsp-perm-now">
			<div class="bsp-perm-now-title">${__("Already allowed")} — ${frappe.utils.escape_html(data.role || "")}</div>
			${body}
		</div>`;
}

function _right_words(perms) {
	return DOC_RIGHTS
		.filter(([, key]) => perms && perms[key])
		.map(([, , label]) => label)
		.join(", ");
}

function _place_table(groups) {
	const order = ["Warehouse", "Territory", "Employee", "Company"];
	const by_name = {};
	(groups || []).forEach((group) => {
		by_name[group.allow] = group;
	});
	const tabs = order.map((name) => {
		return `<button type="button" class="bsp-place-tab" data-place="${name}">${__(name)}</button>`;
	}).join("");
	const panels = order.map((name) => {
		const group = by_name[name];
		return `<div class="bsp-place-panel" data-place="${name}" hidden>${group ? _one_place_table(group) : ""}</div>`;
	}).join("");
	return `<div class="bsp-place-tabs">${tabs}</div>${panels}`;
}

function _one_place_table(group) {
	const allow = frappe.utils.escape_html(group.allow);
	const all_on = group.rows.length && group.rows.every((row) => row.allowed);
	const rows = (group.rows || []).map((row) => {
			const value = frappe.utils.escape_html(row.value);
			const label = frappe.utils.escape_html(row.label || row.value);
			return `
				<tr class="bsp-perm-row">
					<td>${label}</td>
					<td class="bsp-perm-check">
						<input type="checkbox" data-kind="place" data-action="allow"
							data-allow="${allow}" data-value="${value}"
							${row.allowed ? "checked" : ""}>
					</td>
					<td class="bsp-perm-check">
						<input type="checkbox" data-kind="place" data-action="default"
							data-allow="${allow}" data-value="${value}"
							${row.is_default ? "checked" : ""} ${row.allowed ? "" : "disabled"}>
					</td>
				</tr>`;
		}).join("");
	return `
		<div class="bsp-perm-scroll">
			<table class="bsp-perm-table">
				<thead>
					<tr>
						<th></th>
						<th class="bsp-perm-check">
							<span class="bsp-perm-all">
								<span class="bsp-perm-all-label">${__("All")}</span>
								<input type="checkbox" data-kind="place" data-action="all"
									data-allow="${allow}" ${all_on ? "checked" : ""}>
							</span>
						</th>
						<th class="bsp-perm-check">${__("Default")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		</div>`;
}

function _doc_table(groups) {
	if (!groups.length) {
		return `<p class="bsp-perm-note">${__("Choose a job first.")}</p>`;
	}
	const head = DOC_RIGHTS.map(
		([name, , label]) => `<th class="bsp-perm-check">${label}</th>`,
	).join("");
	const body = groups.map((group) => {
		const rows = (group.rows || []).map((row) => _doc_row(row)).join("");
		return `
			<tr class="bsp-perm-section">
				<td colspan="5">${frappe.utils.escape_html(group.label)}</td>
			</tr>
			${rows}`;
	}).join("");
	return `
		<div class="bsp-perm-scroll">
			<table class="bsp-perm-table">
				<thead>
					<tr>
						<th></th>
						${head}
						<th class="bsp-perm-check">${__("All")}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		</div>`;
}

function _doc_row(row) {
	const doctype = frappe.utils.escape_html(row.doctype);
	const cells = DOC_RIGHTS.map(([name, key]) => {
		return `<td class="bsp-perm-check">
			<input type="checkbox" data-kind="doc" data-action="${name}"
				data-doctype="${doctype}" ${row.perms[key] ? "checked" : ""}>
		</td>`;
	}).join("");
	const all_on = DOC_RIGHTS.every(([, key]) => row.perms[key]);
	return `
		<tr class="bsp-perm-row">
			<td>${frappe.utils.escape_html(row.label)}</td>
			${cells}
			<td class="bsp-perm-check">
				<input type="checkbox" data-kind="doc" data-action="all"
					data-doctype="${doctype}" ${all_on ? "checked" : ""}>
			</td>
		</tr>`;
}

function _on_toggle(dialog, data, input, listview) {
	const wrapper = dialog.get_field("matrix").$wrapper;
	wrapper.addClass("bsp-perm-busy");
	const kind = input.dataset.kind;
	const call = kind === "place"
		? _place_call(data, input)
		: _doc_call(data, input);
	if (!call) {
		wrapper.removeClass("bsp-perm-busy");
		return;
	}
	frappe.call({
		method: call.method,
		args: call.args,
		callback() {
			wrapper.removeClass("bsp-perm-busy");
			_load(dialog, listview, data.role);
			if (kind === "place" && listview && listview.refresh) {
				listview.refresh();
			}
		},
		error() {
			wrapper.removeClass("bsp-perm-busy");
			input.checked = !input.checked;
		},
	});
}

function _place_call(data, input) {
	const group = (data.places || []).find((item) => item.allow === input.dataset.allow);
	if (!group) {
		return null;
	}
	const checked = input.checked ? 1 : 0;
	let changes;
	if (input.dataset.action === "default") {
		changes = group.rows
			.filter((row) => row.allowed || row.value === input.dataset.value)
			.map((row) => ({
				allow: group.allow,
				for_value: row.value,
				allowed: 1,
				is_default: checked && row.value === input.dataset.value ? 1 : 0,
			}));
	} else if (input.dataset.action === "all") {
		changes = group.rows.map((row, index) => ({
			allow: group.allow,
			for_value: row.value,
			allowed: checked,
			is_default: checked && index === 0 ? 1 : 0,
		}));
	} else {
		const has_other = group.rows.some(
			(row) => row.value !== input.dataset.value && row.allowed && row.is_default,
		);
		changes = [{
			allow: group.allow,
			for_value: input.dataset.value,
			allowed: checked,
			is_default: checked && !has_other ? 1 : 0,
		}];
	}
	return {
		method: "bsp_engineering.api.user_permission.set_user_permissions",
		args: { user: data.user, changes: JSON.stringify(changes) },
	};
}

function _doc_call(data, input) {
	let row;
	(data.documents || []).some((group) => {
		row = (group.rows || []).find((item) => item.doctype === input.dataset.doctype);
		return !!row;
	});
	if (!row || !data.role) {
		return null;
	}
	const checked = input.checked ? 1 : 0;
	const perms = {
		read: row.perms.read,
		write: row.perms.write,
		create: row.perms.create,
		delete: row.perms.delete,
	};
	if (input.dataset.action === "all") {
		DOC_RIGHTS.forEach(([, key]) => {
			perms[key] = checked;
		});
	} else {
		const spec = DOC_RIGHTS.find(([name]) => name === input.dataset.action);
		perms[spec[1]] = checked;
		if (!checked && spec[1] === "read") {
			DOC_RIGHTS.forEach(([, key]) => {
				perms[key] = 0;
			});
		}
	}
	if (perms.write || perms.create || perms.delete) {
		perms.read = 1;
	}
	perms.submit = row.is_submittable && perms.write ? 1 : 0;
	return {
		method: "bsp_engineering.api.role_permission.set_role_permissions",
		args: {
			role: data.role,
			changes: JSON.stringify([{ doctype: row.doctype, perms }]),
		},
	};
}

function _ensure_style() {
	if (document.getElementById("bsp-perm-style")) {
		return;
	}
	const style = document.createElement("style");
	style.id = "bsp-perm-style";
	style.textContent = `
		.bsp-perm-dialog { width: min(980px, 96vw); }
		.bsp-perm-tabs { display: flex; gap: 0; border-bottom: 1px solid #e6e6e6; margin-bottom: 12px; }
		.bsp-perm-tab-btn {
			border: none; background: transparent; padding: 8px 14px; cursor: pointer;
			font-weight: 600; color: #667085;
		}
		.bsp-perm-tab-btn.active { color: #1b7a4a; border-bottom: 2px solid #1b7a4a; }
		.bsp-place-tabs { display: flex; gap: 6px; margin: 0 0 8px; }
		.bsp-place-tab {
			border: 1px solid #d0d5dd; background: #fff; border-radius: 6px;
			padding: 6px 12px; cursor: pointer; font-weight: 600; color: #344054;
		}
		.bsp-place-tab.active { background: #1b7a4a; border-color: #1b7a4a; color: #fff; }
		.bsp-perm-all { position: relative; display: inline-flex; align-items: center; justify-content: center; }
		.bsp-perm-all-label {
			position: absolute; right: calc(100% + 8px); white-space: nowrap;
			text-transform: none; letter-spacing: 0; font-size: 11px; font-weight: 700;
		}
		.bsp-perm-now { border: 1px solid #d7ead4; background: #f7fbf7; padding: 10px 12px 4px; margin-bottom: 12px; }
		.bsp-perm-now-title, .bsp-perm-give-title { font-weight: 700; font-size: 15px; margin-bottom: 6px; }
		.bsp-perm-block-title { color: #1b7a4a; font-weight: 700; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; margin: 8px 0 4px; }
		.bsp-perm-now ul { margin: 0 0 8px 18px; padding: 0; }
		.bsp-perm-note { color: #667085; font-size: 12px; margin: 0 0 8px; }
		.bsp-perm-scroll { max-height: 42vh; overflow: auto; border: 1px solid #e6e6e6; margin-bottom: 12px; }
		.bsp-perm-scroll-short { max-height: 28vh; }
		.bsp-perm-table { width: 100%; border-collapse: collapse; }
		.bsp-perm-table th, .bsp-perm-table td { padding: 8px 12px; border-bottom: 1px solid #eee; }
		.bsp-perm-table thead th { position: sticky; top: 0; background: #fff; z-index: 1; font-size: 12px; text-align: left; }
		.bsp-perm-table thead th.bsp-perm-check { text-align: center; }
		.bsp-perm-check { width: 88px; text-align: center; vertical-align: middle; }
		.bsp-perm-section td { background: #f4f7f5; color: #1b7a4a; font-weight: 700; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; }
		.bsp-perm-row:nth-child(even) td { background: #fbfbfb; }
		.bsp-perm-table input[type="checkbox"] {
			accent-color: #2e7d32;
			width: 16px;
			height: 16px;
			margin: 0 !important;
			position: static !important;
			cursor: pointer;
		}
		.bsp-perm-empty { padding: 24px 8px; }
		.bsp-perm-busy { pointer-events: none; opacity: .65; }
	`;
	document.head.appendChild(style);
}

_ensure_style();

frappe.ui.form.on("User", {
	refresh(frm) {
		if (frm.is_new() || !frappe.user.has_role("System Manager")) {
			return;
		}
		frm.add_custom_button(__("Manage Permissions"), () => {
			bsp_engineering.user_permission.open(frm.doc.name);
		});
	},
});

frappe.listview_settings["User Permission"] =
	frappe.listview_settings["User Permission"] || {};

(() => {
	const settings = frappe.listview_settings["User Permission"];
	const previous = settings.onload;
	settings.onload = function (listview) {
		if (previous) {
			previous.call(this, listview);
		}
		if (!frappe.user.has_role("System Manager")) {
			return;
		}
		listview.page.add_button(
			__("Manage Permissions"),
			() => {
				const checked = listview.get_checked_items();
				const same_user =
					checked.length &&
					checked.every((row) => row.user === checked[0].user);
				bsp_engineering.user_permission.open(
					same_user ? checked[0].user : null,
					listview,
				);
			},
			{ btn_class: "btn-primary" },
		);
	};
})();
