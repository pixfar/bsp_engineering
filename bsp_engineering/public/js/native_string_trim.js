// Frappe's desk bundle ships an old core-js polyfill that replaces the
// browser's own String.prototype.trim / trimStart / trimEnd with a
// regex-based version that is ~200x slower (measured: 817 ms vs 4 ms for
// 200,000 calls). Vue calls trim() on every class it renders, so on POS
// screens this alone cost hundreds of milliseconds per page switch on a
// phone. The browser's own implementations are spec-compliant; take them
// back from a clean iframe realm (they work on this realm's strings).
(function restore_native_string_trim() {
	const is_native = (fn) => typeof fn === "function" && /\[native code\]/.test(Function.prototype.toString.call(fn));
	const names = ["trim", "trimStart", "trimEnd", "trimLeft", "trimRight"];
	if (names.every((name) => !String.prototype[name] || is_native(String.prototype[name]))) return;
	if (typeof document === "undefined" || !document.documentElement) return;

	let frame;
	try {
		frame = document.createElement("iframe");
		frame.style.display = "none";
		document.documentElement.appendChild(frame);
		const clean = frame.contentWindow && frame.contentWindow.String && frame.contentWindow.String.prototype;
		if (!clean) return;
		for (const name of names) {
			const native = clean[name];
			if (is_native(native) && !is_native(String.prototype[name])) {
				Object.defineProperty(String.prototype, name, {
					value: native,
					writable: true,
					configurable: true,
					enumerable: false,
				});
			}
		}
	} catch (e) {
		// Keep the polyfill if anything goes wrong -- slower, but correct.
	} finally {
		if (frame) frame.remove();
	}
})();
