# Homepage visual assets

Owner reference: `codex-clipboard-dd3a0a15-69b4-435a-8602-fe7c41eb3d60.png` (full-page supplied design).

Both raster assets were derived using the built-in image generation tool, not an external paid API or music provider. These are visual approximations from a flattened reference, not recovered original design layers.

- `home-watercolor-v1.png`: mint paper watercolor background, five colored notes upper left, pipa upper right, flute/red tassel lower left, guzheng lower right, quiet middle. No phone frame, status bar, words, cards or controls. Generated 2026-09-12 from the Owner reference; original file `exec-77893b5a-f765-4e08-9e44-f6a51ef58122.png`.
- `home-icons-v2.png`: 2172 × 724 sprite, three equal square cells: jade waveform, mint medical document/upload cloud, cream-gold checklist. Use CSS `background-size: 300% 100%` at positions 0%, 50%, 100%; clip with rounded corners/circles. Original `exec-8758c6a8-9085-41d9-a4bf-416c01a5e9c1.png`.
- `home-icons-v1.png`: rejected draft with baked checkerboard; retained as prior work but must not be referenced by UI.

## Final icon edit prompt

Use case: precise-object-edit. Edit target: the immediately preceding three-icon sheet. Keep the SAME three icon identities, jade/cream color family, polished illustrated shading and order. Change ONLY backgrounds and sizing to create a production CSS sprite: exactly 3:1 landscape canvas, three equal square cells edge-to-edge with NO gaps, NO margins. Cell 1 LEFT: full-bleed jade green gradient filling its entire square, existing white waveform and four dots centered at 80% cell width, NO enclosing border. Cell 2 MIDDLE: uniform pale mint #c5eedb fills its entire square; medical document plus coral cross and green upload cloud centered at 66% cell width. Cell 3 RIGHT: uniform pale cream gold #faebcf fills its entire square; white checklist with three rings/checkmark and golden lines centered at 66% cell width. These will be clipped into rounded square/circles by CSS. All square cell backgrounds reach every edge. Absolutely NO checkerboard, NO transparency pattern, no text, no lettering, no extra icons, no shadows outside cells. Keep canvas exactly three equal square panels horizontally.

Background prompt specification is recorded above; text and controls are rendered by Vue, never baked into the background.
