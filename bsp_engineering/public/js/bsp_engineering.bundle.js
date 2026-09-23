// Desk-wide scripts for bsp_engineering. Loaded as a Frappe bundle (see
// app_include_js in hooks.py) so every `bench build` gets a new hashed file
// name -- a plain /assets/... path is cached by browsers for 12 hours and
// keeps serving old code after a change.
import "./bsp_column_picker.js";
